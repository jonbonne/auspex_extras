#pragma once

#include <map>
#include <mutex>
#include <array>
#include <vector>
#include <string>
#include <thread>
#include <memory>
#include <dlfcn.h>
#include <cstdint>
#include <cstring>
#include <stdexcept>

#include <rclcpp/rclcpp.hpp>

#include <pluginlib/class_loader.hpp>
#include <auspex_util_core/parameterizable_object.hpp>

namespace auspex
{
namespace emu
{
typedef void (*snes_video_refresh_t)(const uint16_t*, unsigned, unsigned);
typedef void (*snes_audio_sample_t)(uint16_t, uint16_t);
typedef int16_t (*snes_input_state_t)(bool, unsigned, unsigned, unsigned);
typedef void (*snes_input_poll_t)(void);
typedef rclcpp::executors::MultiThreadedExecutor EmulationRunner;

class EmuConfig : public util::ParameterizableObject
{
public:
    EmuConfig(const std::string& name);
    ~EmuConfig() override;
    std::string m_rom_file;
    std::string m_emu_type;
    std::string m_rom_dir;

    std::string getRomFile() const;
    std::string getStateFile(const uint8_t& index) const;
    std::string getMemFile(const uint8_t& type) const;

protected:
    rcl_interfaces::msg::SetParametersResult parametersCallback(const std::vector<rclcpp::Parameter>& parameters) override;
};

class AuspexEmulator
{
public:
    AuspexEmulator();
    virtual ~AuspexEmulator();
    static bool init(const std::string& name);
    static void shutdown();
    static bool ok();
    static void spin_some();

protected:
    static std::unique_ptr<EmuConfig> s_config;
    // video
    size_t m_video_frameskip_idx{0};
    // audio
    std::vector<uint16_t> m_soundbuf_raw;
    // state
    bool m_running{false};
    uint8_t m_state;
    uint8_t m_index;

    // interface
    virtual bool initialize();
    virtual void cycleUpdate() = 0;
    virtual void video_refresh(const uint16_t *data, unsigned width, unsigned height) = 0;
    virtual void audio_sample(uint16_t left, uint16_t right) = 0;
    virtual int16_t input_state(bool port, unsigned device, unsigned index, unsigned id) = 0;
    virtual void input_poll() = 0;

    unsigned getMemory(const uint8_t& type, uint8_t*& data);

private:
    bool loadRom(const std::string& rom_file);
    void run();
    bool running();
    void teardown();

    bool saveMem(const uint8_t& type) const;
    bool loadMem(const uint8_t& type);
    bool saveState(const uint8_t& index) const;
    bool loadState(const uint8_t& index);

    static std::mutex s_video_mutex;
    static std::mutex s_audio_mutex;
    static std::mutex s_input_mutex;
    static pluginlib::ClassLoader<AuspexEmulator> s_emulator_loader;
    static std::shared_ptr<AuspexEmulator> s_rom_emulation;
    static std::unique_ptr<EmulationRunner> s_runner;

    void* m_emulator{nullptr};
    std::unique_ptr<std::thread> m_rt_thread;
    std::mutex m_run_mutex;
    std::vector<uint8_t> m_rom;
    std::vector<uint8_t> m_sram;

    std::vector<uint8_t> loadFile(const std::string &file_path);
    void createRTT();

    // libsnes.so interface link
    void (*snes_init)();
    void (*snes_term)();
    void (*snes_load_cartridge_normal)(void*, const void*, size_t);
    void (*snes_load_cartridge_super_game_boy)(void*, const void*, size_t, void*, const void*, size_t);
    void (*snes_set_cartridge_basename)(void*);
    void (*snes_unload_cartridge)(void);
    uint8_t* (*snes_get_memory_data)(unsigned);
    unsigned (*snes_get_memory_size)(unsigned);
    void (*snes_set_video_refresh)(snes_video_refresh_t);
    void (*snes_set_audio_sample)(snes_audio_sample_t);
    void (*snes_set_input_state)(snes_input_state_t);
    void (*snes_set_input_poll)(snes_input_poll_t);
    void (*snes_set_controller_port_device)(unsigned, unsigned);
    unsigned (*snes_serialize_size)(void);
    bool (*snes_serialize)(uint8_t*, unsigned);
    bool (*snes_unserialize)(const uint8_t*, unsigned);
    void (*snes_power)();
    void (*snes_reset)();
    void (*snes_run)();
    void (*snes_cheat_reset)();
    void (*snes_cheat_set)(unsigned, bool, const char*);
};
}  // namespace emu
}  // namespace auspex
