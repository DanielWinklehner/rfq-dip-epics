cmake_minimum_required(VERSION 3.5)

set(CMAKE_SYSTEM_NAME  Generic)
project(OptimizedSerialRW LANGUAGES CXX C ASM)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED PROG_TYPE)
    set(PROG_TYPE "wiring")
    message(STATUS "PROG_TYPE (programmer) not defined, assuming Arduino bootloader and using programmer 'writing'" )
endif()
if(NOT DEFINED USBPORT)
    message(FATAL_ERROR "USBPORT must be defined. CMake will exit." )
endif()

## Variables regarding the AVR chip
# Notes:
# Baud 2400, 16Mhz F_CPU, with U2X enabled gives 0% error, but is very slow
# Baud 19200, 16Mhz F_CPU, with U2X enabled gives +-0.2% error
# Baud 20000, supposedly has a 0% error rate, need to try it out.
# Baud 76800, 16Mhz F_CPU, with U2X enabled gives +-0.2% error
# EPICS async seems to be unable to handle anything above 20kbuad
#
# Max UBRR = 2^12 (4096)
# UBRR = ( F_CPU / ( 8 * BAUD) ) - 1 (On U2X)
# BAUD = ( F_CPU / ( 8 * (UBRR +1)) ) (On U2X)
# Err% = ((BAUD_{closest} / Baud) - 1)

if(NOT DEFINED MCU)
    set(MCU   atmega2560)
    message(STATUS "MCU not defined, assuming Arduino Mega (atmega2560)" )
endif()
if(NOT DEFINED F_CPU)
    set(F_CPU   16000000)
    message(STATUS "MCU not defined, assuming Arduino standard at 16 Mhz" )
endif()

#set(BAUD  2400)
if(NOT DEFINED BAUD)
    set(BAUD 19200)
    message(STATUS "BAUD not defined, assuming 19200" )
endif()
#set(BAUD 76800)  # EPICS asyn driver does not seem to work bauds above 200k
add_definitions(-DF_CPU=${F_CPU} -DBAUD=${BAUD})

# Nothing should be changed below this line.
# ----------------------------------------------------------------

# program names
set(AVRCPP   avr-g++)
set(AVRC     avr-gcc)
set(AVRSTRIP avr-strip)
set(OBJCOPY  avr-objcopy)
set(OBJDUMP  avr-objdump)
set(AVRSIZE  avr-size)
set(AVRDUDE  avrdude)

# set compiler
set(CMAKE_CXX_COMPILER ${AVRCPP})
set(CMAKE_C_COMPILER   ${AVRC})
set(CMAKE_ASM_COMPILER ${AVRC})

## Compiler flags
set(FLAGS_MAIN "-mmcu=${MCU}")
set(FLAGS_WARNINGS "-Wall -Wextra -Wpedantic")
set(FLAGS_DEBUG "-g -ggdb")
set(FLAGS_RELEASE "-Os")
set(FLAGS_TUNING "-ffunction-sections -fdata-sections")
set(FLAGS_LINKER "-lm -lprintf_flt -Wl,-u,vfprintf -Wl,--gc-sections -Wl,--relax -flto")

set(CMAKE_C_FLAGS   "${CMAKE_C_FLAGS} ${FLAGS_MAIN} ${FLAGS_WARNINGS} ${FLAGS_TUNING} ${FLAGS_LINKER}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++17 ${FLAGS_MAIN} ${FLAGS_WARNINGS} ${FLAGS_TUNING} ${FLAGS_LINKER}")
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} ${FLAGS_DEBUG}")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} ${FLAGS_DEBUG}")
set(CMAKE_C_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} ${FLAGS_RELEASE}")
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} ${FLAGS_RELEASE}")

## Important project paths
set(BASE_PATH    "${${PROJECT_NAME}_SOURCE_DIR}")
set(INC_PATH     "${BASE_PATH}/include")
set(SRC_PATH     "${BASE_PATH}/src")
set(LIB_DIR_PATH "${BASE_PATH}/lib")

## Libraries
# Note: libraries need to always be recompiled with the binary because of definitions defined in the project need to be passed through.
file(GLOB_RECURSE LIB_SRC LIST_DIRECTORIES true CONFIGURE_DEPENDS
  ${LIB_DIR_PATH}/*.cpp)
set(LIB_INC_PATH
  "${LIB_DIR_PATH}/libstaticio/include")

## Project Setup
include_directories(${INC_PATH} ${LIB_INC_PATH})
add_executable(${PROJECT_NAME}
  "src/main.cpp"
  "src/usart.cpp"
  "src/eval.cpp"
  ${LIB_SRC})
set_target_properties(${PROJECT_NAME} PROPERTIES OUTPUT_NAME "${PROJECT_NAME}.elf")

# Compiling targets
add_custom_target(copy_prestrip ALL
  COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_BINARY_DIR}/${PROJECT_NAME}.elf" "${CMAKE_BINARY_DIR}/${PROJECT_NAME}-nostrip.elf"
  DEPENDS ${PROJECT_NAME})
add_custom_target(strip ALL
  COMMAND ${AVRSTRIP} "${PROJECT_NAME}.elf"
  DEPENDS copy_prestrip)
add_custom_target(hex ALL
  COMMAND ${OBJCOPY} -R .eeprom -O ihex "${PROJECT_NAME}.elf" "${PROJECT_NAME}.hex"
  DEPENDS strip)
add_custom_target(disassemble ALL
  COMMAND ${OBJDUMP} -S "${PROJECT_NAME}.elf" > "${PROJECT_NAME}.lst"
  DEPENDS strip)
add_custom_target(eeprom
  COMMAND ${OBJCOPY} -j .eeprom --change-section-lma .eeprom=0 -O ihex "${PROJECT_NAME}.elf" "${PROJECT_NAME}.eeprom"
  DEPENDS strip)

# Flash targets
add_custom_target(flash
  COMMAND ${AVRDUDE} -v -c ${PROG_TYPE} -p ${MCU} -b 115200 -P ${USBPORT} -D -U flash:w:${PROJECT_NAME}.hex:i
  DEPENDS hex)

# Utilities targets
add_custom_command(TARGET hex POST_BUILD
    COMMAND ${AVRSIZE} -C --mcu=${MCU} "${PROJECT_NAME}.elf"
    WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Running size check..."
)

set_directory_properties(PROPERTIES
  ADDITIONAL_MAKE_CLEAN_FILES "${PROJECT_NAME}.hex;${PROJECT_NAME}.eeprom;${PROJECT_NAME}.lst")

# Release by default
if (NOT CMAKE_BUILD_TYPE OR CMAKE_BUILD_TYPE STREQUAL "")
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE)
endif()

## Config logging
message("* ")
message("* Project Name:\t${PROJECT_NAME}")
message("* Project Source:\t${SRC_PATH}")
message("* Project Include:\t${INC_PATH}")
message("* Library Include:\t${LIB_INC_PATH}")
message("* ")
message("* Project Source Files:\t${SRC_FILES}")
message("* Library Source Files:\t${LIB_SRC_FILES}")
message("* ")
message("* C Flags:\t${CMAKE_C_FLAGS}")
message("* ")
message("* CXX Flags:\t${CMAKE_C_FLAGS}")
message("* Avrdude Flags:\t -c ${PROG_TYPE} -p ${MCU} -b 115200 -P ${USBPORT} -D -U flash:w:${PROJECT_NAME}.hex:i")
message("* ")
message("Build type: ${CMAKE_BUILD_TYPE}")


