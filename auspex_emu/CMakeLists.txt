cmake_minimum_required(VERSION 3.5)
project(auspex_emu)

# build libsnes.so
#add_subdirectory(snes9x-libsnes)
# Include the ExternalProject module
include(ExternalProject)
include_directories(/usr/include)
set(SNES9X_SOURCE_DIR ${CMAKE_SOURCE_DIR}/snes9x-libsnes/unix)
set(SNES9X_INCLUDE_DIR ${CMAKE_INSTALL_PREFIX}/include/${PROJECT_NAME})
set(SNES9X_LIB_DIR ${CMAKE_INSTALL_PREFIX}/lib)
# Define the subproject build
ExternalProject_Add(
    snes9x-libsnes
    SOURCE_DIR ${SNES9X_SOURCE_DIR}
    #CONFIGURE_COMMAND ${SNES9X_SOURCE_DIR}/configure --enable-zsnes-asm
    CONFIGURE_COMMAND touch ${SNES9X_SOURCE_DIR}/configure && ${SNES9X_SOURCE_DIR}/configure
    CXXFLAGS=-Wno-unused-variable
    CXXFLAGS=-Wno-implicit-fallthrough
    CXXFLAGS=-Wno-catch-value
    CXXFLAGS=-std=c++98
    CPPFLAGS=-I/usr/include
    CPPFLAGS=-DS9X_SAVESTATES=1
    #CPPFLAGS=-DZSNES_FX=1
    #CPPFLAGS=-DZSNES_C4=1
    LDFLAGS=-L/usr/lib
    BUILD_COMMAND make -j4
    BUILD_IN_SOURCE TRUE
    INSTALL_COMMAND mkdir -p ${SNES9X_LIB_DIR} && cp libsnes.so ${SNES9X_LIB_DIR}/libsnes.so &&
    mkdir -p ${SNES9X_INCLUDE_DIR} && cp libsnes.hpp ${SNES9X_INCLUDE_DIR}/libsnes.hpp
)
link_directories(${SNES9X_LIB_DIR})

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find Deps
find_package(ament_cmake REQUIRED)
find_package(ament_index_cpp REQUIRED)

find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(auspex_util_core REQUIRED)
find_package(auspex_interfaces REQUIRED)
find_package(pluginlib REQUIRED)
find_package(service_msgs REQUIRED)

# Include Directories
include_directories(include
	${rclcpp_INCLUDE_DIRS}
	${auspex_util_core_INCLUDE_DIRS}
	${SNES9X_INCLUDE_DIR}
)

# Add Libraries/Executables
add_library(${PROJECT_NAME} SHARED
    src/auspex_emu.cpp)
target_link_libraries(${PROJECT_NAME} PUBLIC
  ${auspex_interfaces_TARGETS}
  ${auspex_util_core_TARGETS}
  ${service_msgs_TARGETS}
  ${std_msgs_TARGETS}
  ${std_srvs_TARGETS}
  ament_index_cpp::ament_index_cpp
  pluginlib::pluginlib
  rclcpp::rclcpp
  # ... Add non-ROS libraries here
  snes SDL SDL_mixer
)
add_dependencies(${PROJECT_NAME} snes9x-libsnes)

# plugins
add_library(${PROJECT_NAME}_plugins SHARED
    src/snes_sdl_emu.cpp
    src/snes_ros_emu.cpp
)
target_link_libraries(${PROJECT_NAME}_plugins PUBLIC
  ${auspex_interfaces_TARGETS}
  ${service_msgs_TARGETS}
  ${std_msgs_TARGETS}
  ${std_srvs_TARGETS}
  ${auspex_util_core_TARGETS}
  ament_index_cpp::ament_index_cpp
  pluginlib::pluginlib
  rclcpp::rclcpp
  # ... Add non-ROS libraries here
  SDL SDL_mixer
)
add_dependencies(${PROJECT_NAME}_plugins snes9x-libsnes)

add_executable(${PROJECT_NAME}_node
	src/auspex_emu_node.cpp)
target_link_libraries(${PROJECT_NAME}_node PUBLIC
  ${auspex_interfaces_TARGETS}
  ${service_msgs_TARGETS}
  ${std_msgs_TARGETS}
  ${std_srvs_TARGETS}
  ament_index_cpp::ament_index_cpp
  pluginlib::pluginlib
  rclcpp::rclcpp
  # ... Add non-ROS libraries here
  ${PROJECT_NAME}
)
add_dependencies(${PROJECT_NAME}_node snes9x-libsnes)

# Export the plugin to be used by other packages
pluginlib_export_plugin_description_file(${PROJECT_NAME} plugins.xml)

# Install python modules
ament_python_install_package(${PROJECT_NAME})

# Install ROS nodes
install(PROGRAMS
  nodes/libsnes-pygame
  nodes/rom_loader
  nodes/snes-ros-pygame
  DESTINATION lib
)

install(DIRECTORY include
  DESTINATION ${CMAKE_INSTALL_PREFIX}
)

install(DIRECTORY
  config
  launch
  DESTINATION ${CMAKE_INSTALL_PREFIX}/share/${PROJECT_NAME}
)

install(TARGETS
  ${PROJECT_NAME}
  ${PROJECT_NAME}_plugins
  DESTINATION ${CMAKE_INSTALL_PREFIX}/lib
)

install(TARGETS
  ${PROJECT_NAME}_node
  DESTINATION ${CMAKE_INSTALL_PREFIX}/bin
)

ament_export_include_directories(
    include
)
ament_export_libraries(
    ${PROJECT_NAME}_plugins
)
ament_package()
