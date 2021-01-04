#ifndef e53ab5d5_libcom1_com_h
#define e53ab5d5_libcom1_com_h

#include <stdio.h>
#include <stdlib.h>

#include "libutil.hpp"

namespace mist1 {

namespace com1 {
  namespace std = stdx;

#pragma message ("If DEBUG is enabled, there must exist printf support!")
  static constexpr bool DEBUG = false;

  static constexpr uint8_t PRC_QUERY = 1;
  static constexpr uint8_t PRC_SET = 2;
  static constexpr uint8_t PRC_QALL = 3;
  static constexpr uint8_t ERR_UNKNOWN = 10;
  static constexpr uint8_t ERR_CHANNEL_LOOKUP = 11;
  static constexpr uint8_t ERR_PRECISION_TOO_LARGE = 12;
  static constexpr uint8_t ERR_NO_DATA = 15;

  namespace detail {
    static constexpr uint8_t OFST_STATEMENT = 0;
    static constexpr uint8_t OFST_Q_CH_IDEN = 3;
    static constexpr uint8_t OFST_Q_CH_NUM = 4;
    static constexpr uint8_t OFST_Q_PRCN = 5;
    static constexpr uint8_t OFST_S_CH_IDEN = 1;
    static constexpr uint8_t OFST_S_CH_NUM = 2;
    static constexpr uint8_t OFST_S_FLT = 3;
  }

  constexpr uint16_t i16u_iden(char a, uint8_t b)
  {
     return static_cast<uint16_t>( (a << 8u) | b );
  }

  struct Channel {
    using GetterFunc = float (*)();
    using SetterFunc = void (*)(float);

    char m_idenA;
    uint8_t m_idenB;
    GetterFunc m_getter;
    SetterFunc m_setter;

    // Here for syntactic sugar
    constexpr uint16_t i16u_iden() const
    {
      return com1::i16u_iden(m_idenA, m_idenB);
    }
  };


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

    Channel& index (std::size_t i)
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
} // namespace com1

} // namespace mist1


#define MakeChannelMap(var, N, data)                                                                             \
  static constexpr const mist1::com1::ChannelMap<N> var data;                                                    \
  static_assert(mist1::com1::detail::check_unique(var.m_channels), "Channels are not unique");                   \
  static_assert(mist1::com1::detail::check_no_blank_chnls(var.m_channels), "Blank channels exist in ChannelMap")


#endif // e53ab5d5_libcom1_com_h
