cmake_minimum_required(VERSION 3.10)
project(snes_overlay_streamer)

# Locate the real Python executable (venv or system)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
get_target_property(PYTHON_EXECUTABLE Python3::Interpreter LOCATION)

# Patch the missing get_executable_path() that ament_cmake_python expects
macro(get_executable_path out_var _python_exe)
  # ignore the passed-in target name, always use the interpreter we found
  set(${out_var} "${PYTHON_EXECUTABLE}")
endmacro()

find_package(ament_cmake_python REQUIRED)
ament_python_install_package(${PROJECT_NAME})

# Install ROS nodes
install(PROGRAMS
  nodes/snes_overlay_streamer_node
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
