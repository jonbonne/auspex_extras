#include "auspex_emu/snes_ros_emu.hpp"
#include "auspex_emu/definitions.hpp"

namespace auspex
{
namespace emu
{
// Define constants
const int UPDATE_FREQ = 60;
const int BYTES_PER_SAMPLE = 4; // 2 channels (stereo), 2 bytes per channel (uint16)
const int SOUNDBUF_SIZE = 4096 * BYTES_PER_SAMPLE; // Size of the sound buffer in bytes
const int VIDEO_FRAMESKIP = 1;
const int QUEUE_SIZE = 100;

using SnesEmuState = auspex_interfaces::srv::SnesEmuState;
using SnesMemState = auspex_interfaces::srv::SnesMemState;
using SnesGraphics = auspex_interfaces::srv::SnesGraphics;

SnesROS::SnesROS()
    : AuspexEmulator()
    , m_loop_rate(UPDATE_FREQ)
{
    m_function_group = s_config->m_node_handle->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
}

SnesROS::~SnesROS()
{
}

bool SnesROS::initialize()
{
    if (!AuspexEmulator::initialize())
    {
        return false;
    }
    m_video_pub = s_config->m_node_handle->create_publisher<auspex_interfaces::msg::VideoChunk>("~/video_stream", QUEUE_SIZE);
    m_audio_pub = s_config->m_node_handle->create_publisher<auspex_interfaces::msg::AudioChunk>("~/audio_stream", QUEUE_SIZE);
    m_input_sub = s_config->m_node_handle->create_subscription<auspex_interfaces::msg::InputChunk>("~/input_stream", QUEUE_SIZE, std::bind(&SnesROS::inputCb, this, std::placeholders::_1));

    auto service_qos = rclcpp::QoS(rclcpp::QoSInitialization::from_rmw(rmw_qos_profile_services_default));
    m_emu_state_srv = s_config->m_node_handle->create_service<SnesEmuState>("~/state", std::bind(&SnesROS::emulationStateCb, this, std::placeholders::_1, std::placeholders::_2),
                                                                            service_qos, m_function_group);
    m_mem_state_srv = s_config->m_node_handle->create_service<SnesMemState>("~/mem", std::bind(&SnesROS::memoryStateCb, this, std::placeholders::_1, std::placeholders::_2),
                                                                            service_qos, m_function_group);
    m_graphics_srv = s_config->m_node_handle->create_service<SnesGraphics>("~/vram", std::bind(&SnesROS::graphicsCb, this, std::placeholders::_1, std::placeholders::_2),
                                                                            service_qos, m_function_group);
    return true;
}

void SnesROS::inputCb(const auspex_interfaces::msg::InputChunk::SharedPtr msg)
{
    // std::cout << "Got input! " << std::endl;
    if (msg->port)
    {
        m_port0 = msg->buttons;
    }
    else
    {
        m_port1 = msg->buttons;
    }
}

void SnesROS::cycleUpdate()
{
    m_loop_rate.sleep(); // Approximately 60 FPS
}

void SnesROS::video_refresh(const uint16_t *data, unsigned width, unsigned height)
{
    m_video_frameskip_idx += 1;
    if (m_video_frameskip_idx > VIDEO_FRAMESKIP)
    {
        m_video_frameskip_idx = 0;
        // publish!
        auspex_interfaces::msg::VideoChunk chunk;
        chunk.header.frame_id = s_config->m_node_handle->get_name();
        chunk.header.stamp = s_config->m_node_handle->now();
        // there are width*height pixels, each pixel is 8 * 16bits
        // pitch = 8 * width, length = pitch * height / sizeof(uint16_t)
        chunk.data.insert(chunk.data.end(), data, data + 4 * width * height);
        chunk.width = width;
        chunk.height = height;
        m_video_pub->publish(chunk);
    }
}

void SnesROS::audio_sample(uint16_t left, uint16_t right)
{
    // Append left and right samples to the raw sound buffer
    m_soundbuf_raw.push_back(left);
    m_soundbuf_raw.push_back(right);

    if (m_soundbuf_raw.size() * sizeof(uint16_t) >= SOUNDBUF_SIZE)
    {
        // publish!
        auspex_interfaces::msg::AudioChunk chunk;
        chunk.data.insert(chunk.data.end(), m_soundbuf_raw.begin(), m_soundbuf_raw.end());
        chunk.header.frame_id = s_config->m_node_handle->get_name();
        chunk.header.stamp = s_config->m_node_handle->now();
        m_audio_pub->publish(chunk);
        m_soundbuf_raw.clear();
    }
}

int16_t SnesROS::input_state(bool port, unsigned device, unsigned index, unsigned id)
{
    (void) device;
    (void) index;
    return port ? (m_port0 >> id & 0x1) : (m_port1 >> id & 0x1);
}

void SnesROS::input_poll()
{
    // printf("??? InputPoll ???\n");
}

void SnesROS::emulationStateCb(const std::shared_ptr<SnesEmuState::Request> req,
                               const std::shared_ptr<SnesEmuState::Response> rep)
{
    rep->result = true;
    if (req->command == SAVE)
    {
        rep->message = "[" + std::to_string(req->index) + "] State Saved!";
    }
    else if (req->command == LOAD)
    {
        rep->message = "[" + std::to_string(req->index) + "] State Loaded!";
    }
    else if (req->command == RESET)
    {
        rep->message = "Reset System!";
    }
    else if (req->command == POWER)
    {
        rep->message = "Power Cycle System!";
    }
    else
    {
        rep->message = "Invalid Command!";
        rep->result = false;
        return;
    }
    m_state = req->command;
    m_index = req->index;
}

void SnesROS::memoryStateCb(const std::shared_ptr<SnesMemState::Request> req,
                            const std::shared_ptr<SnesMemState::Response> rep)
{
    uint8_t* data;
    rep->size = AuspexEmulator::getMemory(req->type, data);
    rep->data.assign(data, data + rep->size);
}

void SnesROS::graphicsCb(const std::shared_ptr<SnesGraphics::Request> req,
                         const std::shared_ptr<SnesGraphics::Response> rep)
{
    (void)req;  // trigger
    uint8_t* vram;
    if (AuspexEmulator::getMemory(SYSTEM_VRAM, vram) != VRAM_SIZE)
    {
        std::cerr << "Failed to capture VRAM state." << std::endl;
        return;
    }
    rep->vram.assign(vram, vram + VRAM_SIZE);

    uint8_t* ppu;
    if (!AuspexEmulator::getMemory(SYSTEM_PPU, ppu))
    {
        std::cerr << "Failed to capture PPU Registers." << std::endl;
        return;
    }
    // cast ppu to SPPU struct
    SPPU* ppu_registers = reinterpret_cast<SPPU*>(ppu);
    // extract CGData
    std::copy(std::begin(ppu_registers->CGDATA), std::end(ppu_registers->CGDATA), rep->cgd.data.begin());
    // extract BGData
    for (size_t i = 0; i < MAX_BACKGROUNDS; i++)
    {
        rep->bgd.backgrounds[i].sc_base = ppu_registers->BG[i].SCBase;
        rep->bgd.backgrounds[i].hoffset = ppu_registers->BG[i].HOffset;
        rep->bgd.backgrounds[i].voffset = ppu_registers->BG[i].VOffset;
        rep->bgd.backgrounds[i].size = ppu_registers->BG[i].BGSize;
        rep->bgd.backgrounds[i].name_base = ppu_registers->BG[i].NameBase;
        rep->bgd.backgrounds[i].sc_size = ppu_registers->BG[i].SCSize;
    }
    rep->bgd.bg_mode = ppu_registers->BGMode;
    rep->bgd.bg3_priority = ppu_registers->BG3Priority;
    // extract OAM
    for (size_t i = 0; i < MAX_SPRITES; i++)
    {
        rep->oam.sprites[i].x = ppu_registers->OBJ[i].HPos;
        rep->oam.sprites[i].y = ppu_registers->OBJ[i].VPos;
        rep->oam.sprites[i].hflip = ppu_registers->OBJ[i].HFlip;
        rep->oam.sprites[i].vflip = ppu_registers->OBJ[i].VFlip;
        rep->oam.sprites[i].name = ppu_registers->OBJ[i].Name;
        rep->oam.sprites[i].priority = ppu_registers->OBJ[i].Priority;
        rep->oam.sprites[i].palette = ppu_registers->OBJ[i].Palette;
        rep->oam.sprites[i].size = ppu_registers->OBJ[i].Size;
    }
    rep->oam.tile_address = ppu_registers->OAMTileAddress;
    std::copy(std::begin(ppu_registers->OAMData), std::end(ppu_registers->OAMData), rep->oam.raw_data.begin());
    //uint8_t color_depth{4};
    //uint16_t char_addr = (rep->oam.tile_address << 13) + (8 * color_depth * character_number);
    rep->valid = true;
}
}  // namespace emu
}  // namespace auspex

#include <pluginlib/class_list_macros.hpp>
PLUGINLIB_EXPORT_CLASS(auspex::emu::SnesROS, auspex::emu::AuspexEmulator)
