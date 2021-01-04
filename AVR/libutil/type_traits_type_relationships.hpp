#ifndef d4c36745_libutil_type_traits_type_relationships_h
#define d4c36745_libutil_type_traits_type_relationships_h

#include "type_traits_helper_classes.hpp"

namespace stdx {
  // is_same: https://en.cppreference.com/w/cpp/types/is_same
  template<class T, class U>
  struct is_same: stdx::false_type {};

  template<class T>
  struct is_same<T, T> : stdx::true_type {};

  // is_base_of: https://en.cppreference.com/w/cpp/types/is_base_of
  // TODO: write implementation

  // is_convertible: https://en.cppreference.com/w/cpp/types/is_convertible
  // TODO: write implementation

  // is_layout_compatible: https://en.cppreference.com/w/cpp/types/is_layout_compatible
  // TODO: write implementation

  // is_pointer_interconvertible_base_of: https://en.cppreference.com/w/cpp/types/is_pointer_interconvertible_base_of
  // TODO: write implementation

  // is_invocable: https://en.cppreference.com/w/cpp/types/is_invocable
  // TODO: write implementation
}

#endif // d4c36745_libutil_type_traits_property_queries_h
