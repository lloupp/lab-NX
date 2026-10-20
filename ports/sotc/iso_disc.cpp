#include "iso_disc.h"
#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <limits>
#include <unordered_set>
#include <utility>
#include <vector>

namespace sotc {
namespace {
constexpr uint64_t kSector = 2048;
constexpr uint32_t kMaxDirectoryBytes = 8u * 1024u * 1024u;
uint32_t le32(const uint8_t* p) {
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 |
           uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
struct Record { std::string name; uint32_t lba; uint32_t length; bool directory; };
std::optional<Record> record(const uint8_t* p, size_t available) {
    if (available < 34 || p[0] < 34 || p[0] > available) return std::nullopt;
    const size_t n = p[32];
    if (!n || 33 + n > p[0]) return std::nullopt;
    Record out{std::string(reinterpret_cast<const char*>(p + 33), n),
               le32(p + 2), le32(p + 10), (p[25] & 2) != 0};
    if (n == 1 && (p[33] == 0 || p[33] == 1)) return out;
    const auto version = out.name.find(';');
    if (version != std::string::npos) out.name.resize(version);
    return out;
}
}
void IsoDisc::fail(std::string* error, std::string_view message) {
    if (error) error->assign(message.begin(), message.end());
}
std::string IsoDisc::normalize(std::string_view input) {
    auto prefix = input.find(':');
    if (prefix != std::string_view::npos) {
        std::string device(input.substr(0, prefix));
        for (auto& c : device) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (device != "CDROM0" && device != "CDROM") return {};
        input.remove_prefix(prefix + 1);
    }
    std::string out;
    std::string component;
    auto flush = [&]() -> bool {
        if (component == "..") return false;
        if (component != "." && !component.empty()) {
            const auto v = component.find(';');
            if (v != std::string::npos) component.resize(v);
            if (component.empty()) return false;
            out += '/' + component;
        }
        component.clear();
        return true;
    };
    for (const unsigned char c : input) {
        if (c == '/' || c == '\\') {
            if (!flush()) return {};
        } else if (c < 32 || c >= 127 || c == ':') {
            return {};
        } else {
            component += static_cast<char>(std::toupper(c));
        }
    }
    if (!flush()) return {};
    return out;
}
bool IsoDisc::extentValid(const Entry& e) const {
    return e.start <= image_size_ && e.length <= image_size_ - e.start;
}
bool IsoDisc::open(const std::string& path, std::string* error) {
    std::lock_guard<std::mutex> guard(mutex_);
    image_.close(); image_.clear(); entries_.clear(); image_size_ = 0;
    image_.open(path, std::ios::binary);
    if (!image_) { fail(error, "cannot open ISO"); return false; }
    image_.seekg(0, std::ios::end);
    const auto end = image_.tellg();
    if (end < 0) { fail(error, "ISO size unreadable"); return false; }
    image_size_ = static_cast<uint64_t>(end);
    if (image_size_ < 18 * kSector || image_size_ % kSector != 0) {
        fail(error, "ISO image is truncated or not sector aligned"); return false;
    }
    if (!parse(error)) { image_.close(); entries_.clear(); image_size_ = 0; return false; }
    return true;
}
bool IsoDisc::parse(std::string* error) {
    std::array<uint8_t, 2048> pvd{};
    image_.seekg(16 * kSector);
    image_.read(reinterpret_cast<char*>(pvd.data()), pvd.size());
    if (!image_ || pvd[0] != 1 || std::memcmp(pvd.data() + 1, "CD001", 5) || pvd[6] != 1) {
        fail(error, "ISO9660 primary descriptor missing"); return false;
    }
    auto root = record(pvd.data() + 156, pvd.size() - 156);
    if (!root || !root->directory) { fail(error, "invalid ISO root directory"); return false; }
    struct Pending { std::string path; Entry item; int depth; };
    std::vector<Pending> queue{{"", {uint64_t(root->lba) * kSector, root->length, true}, 0}};
    std::unordered_set<uint64_t> visited;
    for (size_t head = 0; head < queue.size(); ++head) {
        const auto node = queue[head];
        if (node.depth > 12 || !extentValid(node.item) ||
            node.item.length > kMaxDirectoryBytes || queue.size() > 8192) {
            fail(error, "invalid directory extent or traversal limit"); return false;
        }
        if (!visited.insert(node.item.start).second) continue;
        std::vector<uint8_t> directory(static_cast<size_t>(node.item.length));
        image_.clear(); image_.seekg(static_cast<std::streamoff>(node.item.start));
        image_.read(reinterpret_cast<char*>(directory.data()), directory.size());
        if (!image_) { fail(error, "unable to read directory"); return false; }
        for (size_t i = 0; i < directory.size();) {
            const uint8_t bytes = directory[i];
            if (!bytes) { i = ((i / kSector) + 1) * kSector; continue; }
            if (bytes > kSector - i % kSector || bytes > directory.size() - i) {
                fail(error, "cross-sector or truncated ISO record"); return false;
            }
            auto r = record(directory.data() + i, bytes);
            i += bytes;
            if (!r) { fail(error, "bad ISO9660 record"); return false; }
            if (r->name.size() == 1 && (r->name[0] == '\0' || r->name[0] == '\1')) continue;
            auto name = normalize(r->name);
            if (name.empty() || name.find('/', 1) != std::string::npos) {
                fail(error, "unsafe ISO file name"); return false;
            }
            const auto full = node.path + name;
            Entry ent{uint64_t(r->lba) * kSector, r->length, r->directory};
            if (!extentValid(ent) || entries_.size() > 20000) {
                fail(error, "file extent exceeds ISO or entry limit"); return false;
            }
            if (!entries_.emplace(full, ent).second) {
                fail(error, "duplicate ISO path"); return false;
            }
            if (r->directory) queue.push_back({full, ent, node.depth + 1});
        }
    }
    return true;
}
bool IsoDisc::contains(std::string_view path) const {
    const auto norm = normalize(path);
    const auto it = entries_.find(norm);
    return it != entries_.end() && !it->second.directory;
}
std::optional<uint64_t> IsoDisc::fileSize(std::string_view path) const {
    const auto norm = normalize(path);
    const auto it = entries_.find(norm);
    if (it == entries_.end() || it->second.directory) return std::nullopt;
    return it->second.length;
}
std::optional<size_t> IsoDisc::read(std::string_view path, uint64_t offset,
                                    void* destination, size_t count) {
    const auto norm = normalize(path);
    const auto it = entries_.find(norm);
    if (it == entries_.end() || it->second.directory || (count && !destination)) return std::nullopt;
    const Entry& entry = it->second;
    if (offset >= entry.length) return size_t(0);
    const uint64_t size = std::min<uint64_t>({count, entry.length - offset,
                                static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())});
    std::lock_guard<std::mutex> guard(mutex_);
    image_.clear();
    image_.seekg(static_cast<std::streamoff>(entry.start + offset));
    image_.read(static_cast<char*>(destination), static_cast<std::streamsize>(size));
    if (image_.gcount() != static_cast<std::streamsize>(size)) return std::nullopt;
    return static_cast<size_t>(size);
}
}
