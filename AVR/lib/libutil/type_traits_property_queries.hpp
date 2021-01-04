#ifndef d4c36745_libutil_type_traits_property_queries_h
#define d4c36745_libutil_type_traits_property_queries_h

#include "extra.hpp"
#include "type_traits_helper_classes.hpp"

namespace stdx {
  // alignment_of: https://en.cppreference.com/w/cpp/types/alignment_of
  template< class T >
  struct alignment_of : stdx::integral_constant<stdx::size_t, alignof(T)> {};

  // rank: https://en.cppreference.com/w/cpp/types/rank
  template<class T>
  struct rank : public stdx::integral_constant<stdx::size_t, 0> {};

  template<class T>
  struct rank<T[]> : public stdx::integral_constant<stdx::size_t, rank<T>::value + 1> {};

  template<class T, stdx::size_t N>
  struct rank<T[N]> : public stdx::integral_constant<stdx::size_t, rank<T>::value + 1> {};

  // extent: https://en.cppreference.com/w/cpp/types/extent
  template<class T, unsigned N = 0>
  struct extent : stdx::integral_constant<stdx::size_t, 0> {};

  template<class T>
  struct extent<T[], 0> : stdx::integral_constant<stdx::size_t, 0> {};

  template<class T, unsigned N>
  struct extent<T[], N> : stdx::extent<T, N-1> {};

  template<class T, stdx::size_t I>
  struct extent<T[I], 0> : stdx::integral_constant<stdx::size_t, I> {};

  template<class T, stdx::size_t I, unsigned N>
  struct extent<T[I], N> : stdx::extent<T, N-1> {};
}

#endif // d4c36745_libutil_type_traits_property_queries_h
