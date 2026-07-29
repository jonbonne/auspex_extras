cmake_minimum_required(VERSION 3.8)
project(auspex_reality)

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# Install Python modules
ament_python_install_package(${PROJECT_NAME})

# Install ROS nodes
install(PROGRAMS
  nodes/torso-control
  nodes/servobot-gui
  DESTINATION lib/${PROJECT_NAME}
)

# Install launch and default configurations
install(DIRECTORY
  config
  launch
  urdf
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_xmllint REQUIRED)
  ament_xmllint()

  find_package(ament_cmake_lint_cmake REQUIRED)
  ament_lint_cmake()

  find_package(ament_cmake_copyright REQUIRED)
  ament_copyright()

  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(${PROJECT_NAME} ${CMAKE_SOURCE_DIR}
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}
    TIMEOUT 1000
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  )
endif()

ament_package()
