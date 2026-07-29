#pragma once

#include <rclcpp/rclcpp.hpp>
#include <auspex_emu/auspex_emu.hpp>
#include <auspex_interfaces/msg/audio_chunk.hpp>
#include <auspex_interfaces/msg/video_chunk.hpp>
#include <auspex_interfaces/msg/input_chunk.hpp>

#include <auspex_interfaces/srv/snes_emu_state.hpp>
#include <auspex_interfaces/srv/snes_mem_state.hpp>
#include <auspex_interfaces/srv/snes_graphics.hpp>

namespace auspex
{
namespace emu
{
class SnesROS : public AuspexEmulator
{
public:
    SnesROS();
    ~SnesROS() override;

protected:
    rclcpp::Rate m_loop_rate;

    bool initialize() override;
    void cycleUpdate() override;
    void video_refresh(const uint16_t *data, unsigned width, unsigned height) override;
    void audio_sample(uint16_t left, uint16_t right) override;
    int16_t input_state(bool port, unsigned device, unsigned index, unsigned id) override;
    void input_poll() override;

    void emulationStateCb(const std::shared_ptr<auspex_interfaces::srv::SnesEmuState::Request> req,
                          const std::shared_ptr<auspex_interfaces::srv::SnesEmuState::Response> rep);
    void memoryStateCb(const std::shared_ptr<auspex_interfaces::srv::SnesMemState::Request> req,
                       const std::shared_ptr<auspex_interfaces::srv::SnesMemState::Response> rep);
    void graphicsCb(const std::shared_ptr<auspex_interfaces::srv::SnesGraphics::Request> req,
                    const std::shared_ptr<auspex_interfaces::srv::SnesGraphics::Response> rep);

private:
    int16_t m_port0{0};
    int16_t m_port1{0};

    void inputCb(const auspex_interfaces::msg::InputChunk::SharedPtr msg);

    rclcpp::CallbackGroup::SharedPtr m_function_group;
    rclcpp::Publisher<auspex_interfaces::msg::VideoChunk>::SharedPtr m_video_pub;
    rclcpp::Publisher<auspex_interfaces::msg::AudioChunk>::SharedPtr m_audio_pub;
    rclcpp::Subscription<auspex_interfaces::msg::InputChunk>::SharedPtr m_input_sub;

    rclcpp::Service<auspex_interfaces::srv::SnesEmuState>::SharedPtr m_emu_state_srv;
    rclcpp::Service<auspex_interfaces::srv::SnesMemState>::SharedPtr m_mem_state_srv;
    rclcpp::Service<auspex_interfaces::srv::SnesGraphics>::SharedPtr m_graphics_srv;
};
}  // namespace emu
}  // namespace auspex
