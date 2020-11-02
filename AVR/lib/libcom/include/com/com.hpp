#ifndef COM_COM_HPP
#define COM_COM_HPP

#include <stdio.h>
#include <stdlib.h>

namespace Comm {
  static constexpr uint8_t PRC_QUERY = 1;
  static constexpr uint8_t PRC_SET = 2;
  static constexpr uint8_t PRC_QALL = 3;
  static constexpr uint8_t ERR_UNKNOWN = 10;
  static constexpr uint8_t ERR_CHANNEL_LOOKUP = 11;
  static constexpr uint8_t ERR_PRECISION_TOO_LARGE = 12;

  namespace detail {
    static constexpr uint8_t OFST_STATEMNT = 0;
    static constexpr uint8_t OFST_Q_CH_IDEN = 3;
    static constexpr uint8_t OFST_Q_CH_NUM = 4;
    static constexpr uint8_t OFST_Q_PRCN = 5;
    static constexpr uint8_t OFST_S_CH_IDEN = 1;
    static constexpr uint8_t OFST_S_CH_NUM = 2;
    static constexpr uint8_t OFST_S_FLT = 3;
  }

#if USE_LIBCOM == 1
  using GetterFunc = float (*)();
  using SetterFunc = void (*)(float);

  struct Channel {
      char iden;
      uint8_t num;
      GetterFunc getter;
      SetterFunc setter;
  };

  template <size_t N>
  struct ChannelMap {
    Channel channels[N];

    // Linear search may seen like a bad idea, but it allows the compiler to
    // optimize more heavily (esp. on -O3) since all the lookup values are known
    // at compile time.
    constexpr const Channel& at(const char& iden, const uint8_t& num, uint8_t* error) const {
      *error=1;
      for (const auto& channel: channels)
      {
          DEBUG_PRINT("Checking: %c %hhu\n", channel.iden, channel.num);
          if (channel.iden == iden && channel.num == num) {
              *error=0;
              return channel;
            }
      }
      return channels[0];
    }

    constexpr const Channel& operator [](size_t idx) const {
      return channels[idx];
    }

    constexpr size_t size() const {
      return N;
    }
  };

#endif
}

#endif
