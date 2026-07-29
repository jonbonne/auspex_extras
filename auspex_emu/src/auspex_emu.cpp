#include <iostream>
#include <fstream>
#include <ctime>
#include <filesystem>

#include <functional>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>

#include <ament_index_cpp/get_package_share_directory.hpp>

#include "auspex_emu/auspex_emu.hpp"
#include "auspex_emu/definitions.hpp"

namespace auspex
{
namespace emu
{
unsigned long nowMs()
{
    // Get the current processor time in clock ticks
    std::clock_t now = std::clock();

    // Convert clock ticks to milliseconds
    unsigned long milliseconds = now * 1000 / CLOCKS_PER_SEC;

    return milliseconds;
}

EmuConfig::EmuConfig(const std::string& name)
    : util::ParameterizableObject(name, "/emulators")
{
    m_node_handle->declare_parameter("rom_file", "");
    m_node_handle->declare_parameter("emu_type", "auspex::emu::SnesSDL");
    m_node_handle->declare_parameter("rom_dir", "/root/roms");
}

EmuConfig::~EmuConfig()
{

}

std::string EmuConfig::getRomFile() const
{
    std::filesystem::path rom_dir(m_rom_dir);
    return rom_dir.append(m_rom_file);
}

std::string EmuConfig::getStateFile(const uint8_t& index) const
{
    // auto rom_file_base = std::filesystem::path(m_rom_file).stem().string();
    std::filesystem::path rom_dir(m_rom_dir);
    return rom_dir.append(m_rom_file + ".bin" + std::to_string(index));
}

std::string EmuConfig::getMemFile(const uint8_t& type) const
{
    std::string ret;
    std::filesystem::path rom_dir(m_rom_dir);
    auto rom_file_dir = std::filesystem::path(m_rom_file).parent_path().string();
    auto rom_file_base = std::filesystem::path(m_rom_file).stem().string();
    if (rom_file_dir.find(m_rom_dir) == 0)
    {
        rom_file_dir.erase(0, m_rom_dir.length());
    }
    switch (type)
    {
    case CARTRIDGE_RAM:
        ret = rom_file_base + ".srm";
        break;
    case CARTRIDGE_RTC:
        ret = rom_file_base + ".rtc";
        break;
    case GAME_BOY_RAM:
        ret = rom_file_base + ".dmgsrm";
        break;
    case GAME_BOY_RTC:
        ret = rom_file_base + ".dmgrtc";
        break;
    };
    return (rom_dir / std::filesystem::path(rom_file_dir)).append(ret);
}

rcl_interfaces::msg::SetParametersResult EmuConfig::parametersCallback(const std::vector<rclcpp::Parameter>& parameters)
{
    rcl_interfaces::msg::SetParametersResult result;
    result.successful = true;
    result.reason = "success";

    for (const auto& parameter : parameters)
    {
        RCLCPP_INFO(m_node_handle->get_logger(), "EmuConfig -- Updating property [%s] to value [%s]", parameter.get_name().c_str(), parameter.value_to_string().c_str());
        if (parameter.get_name().compare("rom_file") == 0)
        {
            auto rom_file = parameter.value_to_string();
            if (!rom_file.empty())
            {
                m_rom_file = parameter.value_to_string();
                RCLCPP_INFO(m_node_handle->get_logger(), "EmuConfig -- Loading ROM [%s]", m_rom_file.c_str());
            }
            else
            {
                result.successful = false;
                result.reason = "Failed to set rom_file: Invalid file name.";
            }
        }
        if (parameter.get_name().compare("emu_type") == 0)
        {
            m_emu_type = parameter.value_to_string();
            RCLCPP_INFO(m_node_handle->get_logger(), "EmuConfig -- Emulator Type [%s]", m_emu_type.c_str());
        }
        if (parameter.get_name().compare("rom_dir") == 0)
        {
            m_rom_dir = parameter.value_to_string();
            RCLCPP_INFO(m_node_handle->get_logger(), "EmuConfig -- ROM directory [%s]", m_rom_dir.c_str());
        }
    }
    return result;
}

pluginlib::ClassLoader<AuspexEmulator> AuspexEmulator::s_emulator_loader("auspex_emu", "auspex::emu::AuspexEmulator");
std::shared_ptr<AuspexEmulator> AuspexEmulator::s_rom_emulation;
std::unique_ptr<EmulationRunner> AuspexEmulator::s_runner;
std::unique_ptr<EmuConfig> AuspexEmulator::s_config;
std::mutex AuspexEmulator::s_video_mutex;
std::mutex AuspexEmulator::s_audio_mutex;
std::mutex AuspexEmulator::s_input_mutex;

AuspexEmulator::AuspexEmulator()
    : m_state(POWER)
    , m_index(0)
{
    m_emulator = dlopen("libsnes.so", RTLD_LAZY);
    if (!m_emulator)
    {
        throw std::runtime_error("Failed to load libsnes.so");
    }

    snes_init = (void (*)())dlsym(m_emulator, "snes_init");
    snes_term = (void (*)())dlsym(m_emulator, "snes_term");
    snes_load_cartridge_normal = (void (*)(void*, const void*, size_t))dlsym(m_emulator, "snes_load_cartridge_normal");
    snes_load_cartridge_super_game_boy = (void (*)(void*, const void*, size_t, void*, const void*, size_t))dlsym(m_emulator, "snes_load_cartridge_super_game_boy");
    snes_set_cartridge_basename = (void (*)(void*))dlsym(m_emulator, "snes_set_cartridge_basename");
    snes_unload_cartridge = (void (*)())dlsym(m_emulator, "snes_unload_cartridge");
    snes_get_memory_data = (uint8_t* (*)(unsigned))dlsym(m_emulator, "snes_get_memory_data");
    snes_get_memory_size = (unsigned (*)(unsigned))dlsym(m_emulator, "snes_get_memory_size");
    snes_set_video_refresh = (void (*)(snes_video_refresh_t))dlsym(m_emulator, "snes_set_video_refresh");
    snes_set_audio_sample = (void (*)(snes_audio_sample_t))dlsym(m_emulator, "snes_set_audio_sample");
    snes_set_input_state = (void (*)(snes_input_state_t))dlsym(m_emulator, "snes_set_input_state");
    snes_set_input_poll = (void (*)(snes_input_poll_t))dlsym(m_emulator, "snes_set_input_poll");
    snes_set_controller_port_device = (void (*)(unsigned, unsigned))dlsym(m_emulator, "snes_set_controller_port_device");
    snes_serialize_size = (unsigned (*)(void))dlsym(m_emulator, "snes_serialize_size");
    snes_serialize = (bool (*)(uint8_t*, unsigned))dlsym(m_emulator, "snes_serialize");
    snes_unserialize = (bool (*)(const uint8_t*, unsigned))dlsym(m_emulator, "snes_unserialize");
    snes_power = (void (*)())dlsym(m_emulator, "snes_power");
    snes_reset = (void (*)())dlsym(m_emulator, "snes_reset");
    snes_run = (void (*)())dlsym(m_emulator, "snes_run");
    snes_cheat_reset = (void (*)())dlsym(m_emulator, "snes_cheat_reset");
    snes_cheat_set = (void (*)(unsigned, bool, const char*))dlsym(m_emulator, "snes_cheat_set");

    if (!snes_init || !snes_term || !snes_load_cartridge_normal || !snes_set_video_refresh || !snes_set_audio_sample ||
        !snes_set_input_state || !snes_set_input_poll || !snes_set_controller_port_device || !snes_power || !snes_run ||
        !snes_load_cartridge_super_game_boy || !snes_set_cartridge_basename || !snes_unload_cartridge ||
        !snes_get_memory_data || !snes_get_memory_size || !snes_serialize_size || !snes_serialize || !snes_unserialize ||
        !snes_reset || !snes_cheat_reset || !snes_cheat_set)
    {
        throw std::runtime_error("Failed to load necessary functions from libsnes.so");
    }
    snes_init();
}

AuspexEmulator::~AuspexEmulator()
{
    snes_term();
    if (m_emulator)
    {
        dlclose(m_emulator);
    }
}

bool AuspexEmulator::init(const std::string& name)
{
    // initialize ROM emulation instance
    if (s_rom_emulation)
    {
        std::cout << "Instance already initialized!" << std::endl;
        return true;
    }

    try
    {
        s_config = std::make_unique<EmuConfig>(name);
        s_rom_emulation = s_emulator_loader.createSharedInstance(s_config->m_emu_type);
    }
    catch (const std::exception& e)
    {
        std::cerr << "Failed to load plugin! " << e.what() << std::endl;
        return false;
    }

    if (!s_rom_emulation->initialize())
    {
        std::cerr << "Failed to initialize instance!" << std::endl;
        return false;
    }

    // add nodes to game runner
    rclcpp::ExecutorOptions executor_options = rclcpp::ExecutorOptions();
    s_runner = std::make_unique<EmulationRunner>(executor_options, 8);
    s_runner->add_node(s_config->m_node_handle);

    s_rom_emulation->run();
    return true;
}

void AuspexEmulator::shutdown()
{
    if (!s_rom_emulation)
    {
        std::cerr << "No instance initialized!" << std::endl;
        return;
    }
    s_rom_emulation->teardown();
    s_runner->remove_node(s_config->m_node_handle);
    //s_rom_emulation.reset(); // set to null for another init
    //s_runner.reset();
}

bool AuspexEmulator::ok()
{
    if (!s_rom_emulation)
    {
        std::cerr << "No instance initialized!" << std::endl;
        return false;
    }
    return s_rom_emulation->running();
}

void AuspexEmulator::spin_some()
{
    if (!s_runner)
    {
        std::cerr << "No runner initialized!" << std::endl;
        return;
    }
    if (rclcpp::ok())
    {
        s_runner->spin_once(std::chrono::milliseconds(10));
        // 4MHz
        std::this_thread::sleep_for(std::chrono::nanoseconds(250));
    }
    else
    {
        std::cout << "RCLCPP is down." << std::endl;
    }
}

void AuspexEmulator::run()
{
    std::unique_lock<std::mutex> lock(m_run_mutex);
    if (m_running)
    {
        std::cout << "Already Running!" << std::endl;
        return;
    }
    m_running = true;
    createRTT();
}

bool AuspexEmulator::loadRom(const std::string& rom_file)
{
    if (rom_file.empty())
    {
        RCLCPP_ERROR_STREAM(s_config->m_node_handle->get_logger(), "AuspexEmulator (" << s_config->m_node_handle->get_name() << ") ROM file must be specified in config!");
        return false;
    }
    m_rom = loadFile(rom_file);
    return true;
}

bool AuspexEmulator::initialize()
{
    // get rom_file from config
    if (!loadRom(s_config->getRomFile()))
    {
        std::cerr << "Failed to load ROM!" << std::endl;
        return false;
    }

    if (!s_rom_emulation)
    {
        std::cerr << "Emulator not allocated or ROM not loaded!" << std::endl;
        return false;
    }

    // Setup callbacks
    snes_set_video_refresh([](const uint16_t *data, unsigned width, unsigned height){
            std::unique_lock<std::mutex> lock(s_video_mutex);
            s_rom_emulation->video_refresh(data, width, height);
    });
    snes_set_audio_sample([](uint16_t left, uint16_t right){
            std::unique_lock<std::mutex> lock(s_audio_mutex);
            s_rom_emulation->audio_sample(left, right);
    });
    snes_set_input_state([](bool port, unsigned device, unsigned index, unsigned id) -> int16_t {
            std::unique_lock<std::mutex> lock(s_input_mutex);
            return s_rom_emulation->input_state(port, device, index, id);
    });
    snes_set_input_poll([](){
            s_rom_emulation->input_poll();
    });

    snes_set_controller_port_device(0, 1);
    snes_set_controller_port_device(1, 0);

    std::cout << "[AuspexEmulator] Initialized!" << std::endl;
    return true;
}

bool AuspexEmulator::running()
{
    std::unique_lock<std::mutex> lock(m_run_mutex);
    return m_running;
}

void AuspexEmulator::teardown()
{
    std::unique_lock<std::mutex> lock(m_run_mutex);
    m_running = false;
    if (m_rt_thread->joinable())
    {
        m_rt_thread->join();
    }
    std::cout << "[AuspexEmulator] Teardown!" << std::endl;
}

std::vector<uint8_t> AuspexEmulator::loadFile(const std::string &file_path)
{
    std::cout << "[AuspexEmulator] Loading ROM: " << file_path << std::endl;
    std::ifstream file(file_path, std::ios::binary);
    return std::vector<uint8_t>((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
}

void AuspexEmulator::createRTT()
{
    m_rt_thread = std::make_unique<std::thread>([&](){
        snes_load_cartridge_normal(nullptr, m_rom.data(), m_rom.size());
        loadMem(CARTRIDGE_RAM);
        loadMem(CARTRIDGE_RTC);
        loadMem(GAME_BOY_RAM);
        loadMem(GAME_BOY_RTC);
        while (m_running)
        {
            switch (m_state)
            {
            case POWER:
                snes_power();
                m_state = RUNNING;
                break;
            case RESET:
                snes_reset();
                m_state = RUNNING;
                break;
            case RUNNING:
                snes_run();
                break;
            case SAVE:
                saveState(m_index);
                m_state = RUNNING;
                break;
            case LOAD:
                loadState(m_index);
                m_state = RUNNING;
                break;
            };
            cycleUpdate();
        }
        saveMem(CARTRIDGE_RAM);
        saveMem(CARTRIDGE_RTC);
        saveMem(GAME_BOY_RAM);
        saveMem(GAME_BOY_RTC);
        snes_unload_cartridge();
    });
    pthread_t thread_id = m_rt_thread->native_handle();
    struct sched_param sched_param;
    sched_param.sched_priority = 99; // Priority between 1 and 99 for SCHED_FIFO
    if (pthread_setschedparam(thread_id, SCHED_FIFO, &sched_param) != 0)
    {
        std::cerr << "Failed to set thread scheduling parameters" << std::endl;
        return;
    }
    m_rt_thread->detach();
}

unsigned AuspexEmulator::getMemory(const uint8_t& type, uint8_t*& data)
{
    data = snes_get_memory_data(type);
    return snes_get_memory_size(type);
}

bool AuspexEmulator::loadMem(const uint8_t& type)
{
    unsigned buffer_size = snes_get_memory_size(type);
    if (!buffer_size)
    {
        // memory type not supported for this cartridge
        return false;
    }
    // Create the filename using the index
    std::string filename = s_config->getMemFile(type);

    // Open the file for reading
    std::ifstream file(filename, std::ios::in | std::ios::binary | std::ios::ate);
    if (!file)
    {
        std::cerr << "Failed to open file for reading: " << filename << std::endl;
        return false;
    }

    // Determine the file size and read the content into a buffer
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::cout << "Loading Memory... (" << (buffer_size / 1000.0) << "KB)" << std::endl;
    std::vector<uint8_t> buffer(size);
    if (!file.read(reinterpret_cast<char*>(buffer.data()), buffer.size()))
    {
        std::cerr << "Failed to read SNES state from file: " << filename << std::endl;
        return false;
    }

    uint8_t* data = snes_get_memory_data(type);
    std::memcpy(data, buffer.data(), buffer.size());
    return true;
}

bool AuspexEmulator::saveMem(const uint8_t& type) const
{
    unsigned buffer_size = snes_get_memory_size(type);
    if (!buffer_size)
    {
        // memory type not supported for this cartridge
        return false;
    }
    std::cout << "Saving Memory... (" << (buffer_size / 1000.0) << "KB)" << std::endl;
    uint8_t* data = snes_get_memory_data(type);
    std::vector<uint8_t> buffer(data, data + buffer_size);

    // Create the filename using the index
    std::string filename = s_config->getMemFile(type);

    // Open the file for writing
    std::ofstream file(filename, std::ios::out | std::ios::binary);
    if (!file)
    {
        std::cerr << "Failed to open file for writing: " << filename << std::endl;
        return false;
    }

    // Write the memory buffer to the file
    file.write(reinterpret_cast<char*>(buffer.data()), buffer.size());
    if (!file)
    {
        std::cerr << "Failed to write SNES memory state to file: " << filename << std::endl;
        return false;
    }

    std::cout << "State saved successfully to " << filename << std::endl;
    return true;
}

bool AuspexEmulator::saveState(const uint8_t& index) const
{
    size_t buffer_size = snes_serialize_size();
    std::cout << "Saving State... (" << (buffer_size / 1000.0) << "KB)" << std::endl;
    std::vector<uint8_t> buffer(buffer_size);
    // Serialize the state into the buffer
    if (!snes_serialize(buffer.data(), buffer_size))
    {
        std::cerr << "Failed to serialize SNES state." << std::endl;
        return false;
    }

    // Create the filename using the index
    std::string filename = s_config->getStateFile(index);

    // Open the file for writing
    std::ofstream file(filename, std::ios::out | std::ios::binary);
    if (!file)
    {
        std::cerr << "Failed to open file for writing: " << filename << std::endl;
        return false;
    }

    // Write the buffer to the file
    file.write(reinterpret_cast<char*>(buffer.data()), buffer.size());
    if (!file)
    {
        std::cerr << "Failed to write SNES state to file: " << filename << std::endl;
        return false;
    }

    std::cout << "State saved successfully to " << filename << std::endl;
    return true;
}

bool AuspexEmulator::loadState(const uint8_t& index)
{
    // Create the filename using the index
    std::string filename = s_config->getStateFile(index);

    // Open the file for reading
    std::ifstream file(filename, std::ios::in | std::ios::binary | std::ios::ate);
    if (!file)
    {
        std::cerr << "Failed to open file for reading: " << filename << std::endl;
        return false;
    }

    // Determine the file size and read the content into a buffer
    std::streamsize size = file.tellg();
    file.seekg(0, std::ios::beg);

    std::cout << "Loading State... (" << (size / 1000.0) << "KB)" << std::endl;
    std::vector<uint8_t> buffer(size);
    if (!file.read(reinterpret_cast<char*>(buffer.data()), buffer.size()))
    {
        std::cerr << "Failed to read SNES state from file: " << filename << std::endl;
        return false;
    }

    // Deserialize the buffer back into the SNES emulator state
    if (!snes_unserialize(buffer.data(), buffer.size()))
    {
        std::cerr << "Failed to unserialize SNES state." << std::endl;
        return false;
    }

    std::cout << "State loaded successfully from " << filename << std::endl;
    return true;
}
}  // namespace emu
}  // namespace auspex
