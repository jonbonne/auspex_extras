#include "auspex_emu/auspex_emu.hpp"
#include "auspex_emu/snes_sdl_emu.hpp"

namespace auspex
{
namespace emu
{
// Define constants
const int BYTES_PER_SAMPLE = 4; // 2 channels (stereo), 2 bytes per channel (uint16)
const int NUM_CHANNELS = 4; // Adjust based on your needs
const int SOUNDBUF_SIZE = 2048 * BYTES_PER_SAMPLE; // Size of the sound buffer in bytes
const int VIDEO_FRAMESKIP = 0;

SnesSDL::SnesSDL()
    : AuspexEmulator()
    , m_sound_channel(NUM_CHANNELS)
{
    SnesSDL::init_sdl();
}

SnesSDL::~SnesSDL()
{
    for (int i = 0; i < NUM_CHANNELS; ++i)
    {
        if (m_sound_channel[i])
        {
            Mix_FreeChunk(m_sound_channel[i].get());
        }
    }
    SnesSDL::teardown_sdl();
}

bool SnesSDL::init_sdl()
{
    // Initialize SDL
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_JOYSTICK) != 0)
    {
        std::cerr << "SDL_Init Error: " << SDL_GetError() << std::endl;
        return false;
    }

    if (Mix_OpenAudio(32000, AUDIO_S16LSB, 2, SOUNDBUF_SIZE / BYTES_PER_SAMPLE) == -1)
    {
        std::cerr << "Mix_OpenAudio Error: " << Mix_GetError() << std::endl;
        return false;
    }
    Mix_AllocateChannels(NUM_CHANNELS);
    return true;
}

void SnesSDL::teardown_sdl()
{
    // teardown SDL sound_channel
    Mix_CloseAudio();
    SDL_Quit();
}

void SnesSDL::cycleUpdate()
{
    SDL_PollEvent(&m_current_events);
    switch (m_current_events.type)
    {
    case SDL_QUIT:
        m_running = false;
        break;
    default:
        break;
    }
    SDL_Delay(16); // Approximately 60 FPS
}

void SnesSDL::video_refresh(const uint16_t *data, unsigned width, unsigned height)
{
    m_video_frameskip_idx += 1;
    int pitch = 8 * width;

    if (!m_screen)
    {
        m_screen = SDL_SetVideoMode(width, height, 32, SDL_SWSURFACE);
        if (m_screen == nullptr)
        {
            std::cerr << "SDL_SetVideoMode Error: " << SDL_GetError() << std::endl;
            SDL_Quit();
            return;
        }

        // Create an SDL_Surface from the pixel data
        m_image = SDL_CreateRGBSurfaceFrom(
            (void*)data,      // Your pixel data
            width, height,    // Width, height
            15,          // Depth (bits per pixel)
            pitch,     // Pitch (row size in bytes)
            0x7C00,  // Red mask
            0x03E0,  // Green mask
            0x001F,  // Blue mask
            0x000   // Alpha mask
        );
    }

    if (m_video_frameskip_idx > VIDEO_FRAMESKIP)
    {
        m_video_frameskip_idx = 0;

        // Fill the screen with a black color
        SDL_FillRect(m_screen, nullptr, SDL_MapRGB(m_screen->format, 0, 0, 0));

        // Blit the image onto the screen surface
        SDL_Rect dest;
        dest.x = (m_screen->w - m_image->w) / 2;  // Center the image horizontally
        dest.y = (m_screen->h - m_image->h) / 2;  // Center the image vertically
        SDL_BlitSurface(m_image, nullptr, m_screen, &dest);
        SDL_Flip(m_screen);

    }
}

void SnesSDL::audio_sample(uint16_t left, uint16_t right)
{
    // Implement SDL2 sound handling similar to the Pygame implementation
    try
    {
        // Append left and right samples to the raw sound buffer
        m_soundbuf_raw.push_back(left);
        m_soundbuf_raw.push_back(right);

        // Check if the buffer is full
        if (m_soundbuf_raw.size() * sizeof(Uint16) >= SOUNDBUF_SIZE)
        {
            // Create audio buffer
            Uint8* raw_audio_data = reinterpret_cast<Uint8*>(m_soundbuf_raw.data());
            Uint32 length = SOUNDBUF_SIZE;

            // Create a Mix_Chunk from the raw audio data
            Mix_Chunk* chunk = Mix_QuickLoad_RAW(raw_audio_data, length);
            if (!chunk)
            {
                throw std::runtime_error("Failed to load audio chunk: " + std::string(Mix_GetError()));
            }

            // Queue the chunk for playback on the current channel
            if (Mix_PlayChannel(m_channel_idx, chunk, 0) == -1)
            {
                // something went wrong. immediately free chunk and throw an error.
                Mix_FreeChunk(chunk);
                throw std::runtime_error("Failed to play chunk: " + std::string(Mix_GetError()));
            }

            // Store the new chunk for later cleanup
            if (m_sound_channel[m_channel_idx])
            {
                // older chunks get freed now
                Mix_FreeChunk(m_sound_channel[m_channel_idx].get());
            }
            m_sound_channel[m_channel_idx].reset(chunk);
            Mix_VolumeChunk(m_sound_channel[m_channel_idx].get(), 64);

            // Clear the raw sound buffer
            m_soundbuf_raw.clear();

            // Move to the next channel
            m_channel_idx = (m_channel_idx + 1) % NUM_CHANNELS;
        }
    }
    catch (const std::exception& err)
    {
        std::cerr << "!!! " << err.what() << std::endl;
    }
}

int16_t SnesSDL::input_state(bool port, unsigned device, unsigned index, unsigned id)
{
    // printf("??? InputState ???\n");
    (void)port;
    (void)device;
    (void)index;
    (void)id;
    return 0;
}

void SnesSDL::input_poll()
{
    // printf("??? InputPoll ???\n");
}
}  // namespace emu
}  // namespace auspex

#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(auspex::emu::SnesSDL, auspex::emu::AuspexEmulator)
