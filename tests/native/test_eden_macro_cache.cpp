/* Regression for Eden v0.2.1 MacroEngine::Execute's mid-macro extraction.
 * Build against Eden's pinned ankerl::unordered_dense dependency.
 * -DGE_REPRODUCE_EDEN_UAF=1 intentionally exercises the original ASan failure.
 * This is an isolated container-lifetime test, not a rebuilt Eden emulator.
 */
#include <ankerl/unordered_dense.h>
#include <assert.h>
#include <stdio.h>
#include <vector>

int main(void)
{
    ankerl::unordered_dense::map<unsigned, std::vector<unsigned>> code_map;
    code_map[0] = {11, 22, 33, 44, 55, 66};
    const auto &cached = code_map.at(0);
#ifdef GE_REPRODUCE_EDEN_UAF
    auto &code = code_map[3];
    code.resize(cached.size() - 3); // original invalidated-reference pattern
    for (size_t i = 0; i < code.size(); ++i) code[i] = cached[i + 3];
#else
    std::vector<unsigned> suffix(cached.begin() + 3, cached.end());
    auto &code = code_map[3];
    code = std::move(suffix);
#endif
    assert((code_map.at(3) == std::vector<unsigned>{44, 55, 66}));
    assert((code_map.at(0) == std::vector<unsigned>{11, 22, 33, 44, 55, 66}));
    // Force additional relocations; each suffix must stay intact.
    for (unsigned i = 10; i < 300; ++i) {
        const auto &source = code_map.at(0);
        std::vector<unsigned> suffix(source.begin() + 1, source.end());
        code_map[i] = std::move(suffix);
    }
    assert((code_map.at(299) == std::vector<unsigned>{22, 33, 44, 55, 66}));
    puts("Eden macro-cache relocation regression: PASS (isolated source test)");
}
