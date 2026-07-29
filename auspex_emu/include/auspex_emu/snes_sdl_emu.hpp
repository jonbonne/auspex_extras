#pragma once

#include <SDL/SDL.h>
#include <SDL/SDL_mixer.h>

#include <auspex_emu/auspex_emu.hpp>

namespace auspex
{
namespace emu
{
class SnesSDL : public AuspexEmulator
{
public:
    SnesSDL();
    ~SnesSDL() override;

protected:
    SDL_Event m_current_events;
    // video
    SDL_Surface* m_screen{nullptr};
    SDL_Surface* m_image{nullptr};
    // audio
    std::vector<std::shared_ptr<Mix_Chunk>> m_sound_channel;
    size_t m_channel_idx{0};

    static bool init_sdl();
    static void teardown_sdl();

    void cycleUpdate() override;
    void video_refresh(const uint16_t *data, unsigned width, unsigned height) override;
    void audio_sample(uint16_t left, uint16_t right) override;
    int16_t input_state(bool port, unsigned device, unsigned index, unsigned id) override;
    void input_poll() override;
};
}  // namespace emu
}  // namespace auspex
