#include <iostream>
#include <csignal>

#include "auspex_emu/auspex_emu.hpp"

volatile sig_atomic_t stop_thread = 0;

void signalHandler(int signal)
{
    if (signal == SIGINT || signal == SIGTERM)
    {
        stop_thread = 1;
        auspex::emu::AuspexEmulator::shutdown();
    }
}

int main(int argc, char *argv[])
{
    rclcpp::init(argc, argv);

    // Set up signal handling for SIGINT and SIGTERM
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    try
    {
        if (!auspex::emu::AuspexEmulator::init("auspex_emu"))
        {
            std::cerr << "Failed to initialize!" << std::endl;
            return 1;
        }

        while (!stop_thread and auspex::emu::AuspexEmulator::ok())
        {
            auspex::emu::AuspexEmulator::spin_some();
        }
    }
    catch (const std::exception &ex)
    {
        std::cerr << "Exception: " << ex.what() << std::endl;
        return 1;
    }

    return 0;
}
