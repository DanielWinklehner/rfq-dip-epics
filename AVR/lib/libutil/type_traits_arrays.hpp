#ifndef d4c36745_libutil_type_traits_arrays_h
#define d4c36745_libutil_type_traits_arrays_h

#include "extra.hpp"
#include "type_traits_helper_classes.hpp"

namespace stdx {
  // remove_extent: https://en.cppreference.com/w/cpp/types/remove_extent
  template<class T>
  struct remove_extent { typedef T type; };

  template<class T>
  struct remove_extent<T[]> { typedef T type; };

  template<class T, stdx::size_t N>
  struct remove_extent<T[N]> { typedef T type; };

  template< class T >
  using remove_extent_t = typename remove_extent<T>::type;

  // remove_all_extents: https://en.cppreference.com/w/cpp/types/remove_all_extents
  template<class T>
  struct remove_all_extents { typedef T type;};

  template<class T>
  struct remove_all_extents<T[]> {
      typedef typename remove_all_extents<T>::type type;
  };

  template<class T, stdx::size_t N>
  struct remove_all_extents<T[N]> {
      typedef typename remove_all_extents<T>::type type;
  };

  template< class T >
  using remove_all_extents_t = typename remove_all_extents<T>::type;
}

#endif // d4c36745_libutil_type_traits_arrays_h
