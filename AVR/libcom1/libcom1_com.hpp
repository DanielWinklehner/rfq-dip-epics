#ifndef e53ab5d5_libcom1_com_h
#define e53ab5d5_libcom1_com_h

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>

#include "libutil.hpp"

// Which float formatter to use.
// On Arduino AVR the IDE does not link the float-enabled printf, so avr-libc's dtostre() is used.
// Everywhere else (Teensy, Opta, standalone avr-libc with printf_flt, a PC) snprintf("%g") is used.
// The host tests override this to exercise the dtostre code path off-target.
#ifndef LIBCOM1_USE_DTOSTRE
  #if defined(Arduino_h) && defined(__AVR__)
    #define LIBCOM1_USE_DTOSTRE 1
  #else
    #define LIBCOM1_USE_DTOSTRE 0
  #endif
#endif

namespace mist1 {

namespace com1 {
  namespace std = stdx;

  // If DEBUG is enabled, there must exist printf support!
  static constexpr bool DEBUG = false;

  // Reported by the identity query ("I"). Version 1 is the original q/s/A protocol.
  static constexpr uint8_t PROTOCOL_VERSION = 2;

  // Values returned from processing input in libcom1_eval.hpp to indicate an error or completion in processing an input
  // Everything below ERR_UNKNOWN means "a valid command was processed".
  static constexpr uint8_t PRC_QUERY = 1;     // legacy single query "q01.."
  static constexpr uint8_t PRC_SET = 2;       // "s..", no reply
  static constexpr uint8_t PRC_QALL = 3;      // "A"
  static constexpr uint8_t PRC_GET = 4;       // "g..", single query in plain %g format
  static constexpr uint8_t PRC_SET_ACK = 5;   // "S..", replies "ok"
  static constexpr uint8_t PRC_IDENT = 6;     // "I"
  static constexpr uint8_t PRC_PERIOD = 7;    // "P<ms>", replies "ok"
  static constexpr uint8_t ERR_UNKNOWN = 10;              // ERR0
  static constexpr uint8_t ERR_CHANNEL_LOOKUP = 11;       // ERR4
  static constexpr uint8_t ERR_PRECISION_TOO_LARGE = 12;  // ERR1
  static constexpr uint8_t ERR_BUFFER = 13;               // ERR2, reply does not fit the output buffer
  static constexpr uint8_t ERR_NUM_CHANNELS = 14;         // ERR3, legacy query asked for anything but one channel
  static constexpr uint8_t ERR_NO_DATA = 15;              // nothing to process, no reply
  static constexpr uint8_t ERR_SYNTAX = 16;               // ERR5, malformed command or value
  static constexpr uint8_t ERR_VALUE = 17;                // ERR6, value cannot be represented in the legacy format
  static constexpr uint8_t ERR_NOT_SUPPORTED = 18;        // ERR7, channel is not readable / not writable

  // Offset values to find the byte in question of the input
  namespace detail {
    static constexpr uint8_t OFST_STATEMENT = 0;
    static constexpr uint8_t OFST_Q_CH_IDEN = 3;
    static constexpr uint8_t OFST_Q_CH_NUM = 4;
    static constexpr uint8_t OFST_Q_PRCN = 5;
    static constexpr uint8_t OFST_S_CH_IDEN = 1;
    static constexpr uint8_t OFST_S_CH_NUM = 2;
    static constexpr uint8_t OFST_S_FLT = 3;

    // Longest text one formatted channel value can take, without the terminating NUL.
    // dtostre(prec 6): "+d.dddddde+dd" = 13 chars. snprintf("%g"): "-d.ddddde-dd" = 12 chars.
    static constexpr uint8_t MAX_VALUE_CHARS = 13;
  }

  constexpr uint16_t i16u_iden(char a, uint8_t b)
  {
     return static_cast<uint16_t>( (a << 8u) | b );
  }

  // Each channel has two identifications (one letter and one digit), a getter function, and a setter function.
  //
  // Two callback styles are supported:
  //  - plain:    float get();            void set(float);
  //  - indexed:  float get(uint8_t arg); void set(uint8_t arg, float);
  // The indexed style lets many similar channels share one pair of functions (see IndexedChannel below).
  // A callback may be a null pointer: the channel is then write-only or read-only.
  //
  // This stays an aggregate so that the original `Channel{ 'a', 1, &get, &set }` keeps working
  // (the trailing members are value-initialised to null / 0).
  struct Channel {
    using GetterFunc = float (*)();
    using SetterFunc = void (*)(float);
    using IdxGetterFunc = float (*)(uint8_t);
    using IdxSetterFunc = void (*)(uint8_t, float);

    char m_idenA;
    uint8_t m_idenB;
    GetterFunc m_getter;
    SetterFunc m_setter;
    IdxGetterFunc m_idx_getter;
    IdxSetterFunc m_idx_setter;
    uint8_t m_arg;

    // Here for syntactic sugar
    constexpr uint16_t i16u_iden() const
    {
      return com1::i16u_iden(m_idenA, m_idenB);
    }

    constexpr bool readable() const
    {
      return m_getter != nullptr || m_idx_getter != nullptr;
    }

    constexpr bool writable() const
    {
      return m_setter != nullptr || m_idx_setter != nullptr;
    }

    // Current value. A channel without a getter reads as 0.
    float get() const
    {
      return m_getter ? m_getter() : (m_idx_getter ? m_idx_getter(m_arg) : 0.0f);
    }

    // Does nothing on a channel without a setter.
    void set(float value) const
    {
      if (m_setter)
        m_setter(value);
      else if (m_idx_setter)
        m_idx_setter(m_arg, value);
    }
  };

  // Channel whose callbacks receive `arg`, e.g. an index into a pin table:
  //   IndexedChannel('s', 1, &get_solenoid, &set_solenoid, 0)
  constexpr Channel IndexedChannel(char idenA, uint8_t idenB,
                                   Channel::IdxGetterFunc getter,
                                   Channel::IdxSetterFunc setter,
                                   uint8_t arg)
  {
    return Channel{ idenA, idenB, nullptr, nullptr, getter, setter, arg };
  }


  namespace detail {

    template <std::size_t N>
    constexpr bool check_unique_to_others (
        const Channel (&ch_arr)[N],
        const std::size_t current,
        const std::size_t current_other)  {
      return ( !current || !N || // No check if there are no others to check against
              (
                // Not identical at this `current` and the idx being comapred against
                ch_arr[current].i16u_iden() != ch_arr[current_other].i16u_iden() &&
                ( // Don't continue recursing if it will underflow
                  !current_other ||
                  // Not identical at `current` and the next idx to compare to
                  check_unique_to_others<N>(ch_arr, current, current_other - 1)
                )
              )
             );
    }

    template <std::size_t N>
    constexpr bool check_unique(const Channel (&ch_arr)[N], std::size_t current = N - 1) {
        return (!current || !N || // No check if there are no others to check against
                  (
                    // Span a check: `current` until it hits zero
                    check_unique_to_others(ch_arr, current, current - 1) &&
                    // Check next `current`
                    check_unique(ch_arr, current - 1)
                  ) ); // Recurse to a previous current
    }


    // Note: there's no default constructor for channel, so it is entirely possible
    // that the compiler constructs a channel in channelmap randomly. While it's
    // most sensible to check for 0s, this check may not catch all cases where
    // N is larger than the actual size of the array
    template <std::size_t N>
    constexpr bool check_no_blank_chnls (const Channel (&ch_arr)[N], std::size_t current = N - 1) {
      return ( !current || !N || // Return true if `current` reaches the end or if there are no channels
               ( (ch_arr[current].m_idenA != 0x00 || ch_arr[current].m_idenB != 0x00) && // Not blank at this idx
                 check_no_blank_chnls<N>(ch_arr, current - 1) // Check next element in array
               )
             );
    }

  } // namespace detail

  template <std::size_t N>
  struct ChannelMap {
    const Channel m_channels[N];

    constexpr const Channel& index(size_t i) const
    {
      return m_channels[i];
    }

  private:
    enum class atTag {}; // Stop people from being able to set `current` in the at() function
  public:
    // Linear search may seen like a bad idea, but it allows the compiler to
    // optimize more heavily (esp. on -O3) since all the lookup values are known
    // at compile time.
    // TODO: Return a stdx::reference_wrapper<Channel> instead of just Channel
    // aka. return a reference instead of a copy
    constexpr stdx::expected<Channel, uint8_t> at(
        const uint16_t iden,
        const atTag& = atTag(),
        const std::size_t current = N - 1) const
    {
      return (
            // If the channel we're looking at is the corrent one, then return it
            (iden == m_channels[current].i16u_iden()) ?
               m_channels[current] :
                  ( // Otherwise: keep checking.
                    // If `current` is at the end, then we know it has not found it, so error.
                    current ? at(iden, atTag(), current - 1) :
                        stdx::unexpected<uint8_t>(ERR_CHANNEL_LOOKUP)
                   ));
    }

    constexpr std::size_t size() const {
      return N;
    }
  };

  // Smallest output buffer that can always hold the query-all reply for N channels:
  // 'o', then per channel a value and a ':' (the last ':' becomes the terminating NUL).
  // SerialDevice refuses to compile with a smaller buffer.
  constexpr std::size_t min_out_buffer_size(std::size_t n_channels)
  {
    return n_channels * (static_cast<std::size_t>(detail::MAX_VALUE_CHARS) + 1) + 2;
  }

  // Output buffer needed to also use streaming ("P<ms>"): "t<seq>:<ms>:" in front of the values.
  constexpr std::size_t min_stream_buffer_size(std::size_t n_channels)
  {
    return min_out_buffer_size(n_channels) + 5 + 1 + 10 + 1;
  }
} // namespace com1

} // namespace mist1


#define MakeChannelMap(var, N, data)                                                                             \
  static constexpr const mist1::com1::ChannelMap<N> var data;                                                    \
  static_assert(mist1::com1::detail::check_unique(var.m_channels), "Channels are not unique");                   \
  static_assert(mist1::com1::detail::check_no_blank_chnls(var.m_channels), "Blank channels exist in ChannelMap")


#endif // e53ab5d5_libcom1_com_h
