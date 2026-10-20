#pragma once
// ISO9660 read-only streaming for the original SCUS-97472 disc.
// C++17, no libnx dependency: libnx SD files work through std::ifstream.
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>

namespace sotc {
class IsoDisc {
public:
    bool open(const std::string& image, std::string* error = nullptr);
    bool contains(std::string_view ps2_path) const;
    std::optional<uint64_t> fileSize(std::string_view ps2_path) const;
    // Reads just the requested bytes; EOF yields 0, invalid paths yield nullopt.
    std::optional<size_t> read(std::string_view ps2_path, uint64_t offset,
                               void* destination, size_t count);
    size_t indexedFiles() const { return entries_.size(); }
    static std::string normalize(std::string_view path);
private:
    struct Entry { uint64_t start; uint64_t length; bool directory; };
    bool parse(std::string* error);
    bool extentValid(const Entry& item) const;
    static void fail(std::string* error, std::string_view message);
    mutable std::mutex mutex_;
    std::ifstream image_;
    uint64_t image_size_ = 0;
    std::unordered_map<std::string, Entry> entries_;
};
}
