#ifndef d4c36745_libutil_type_traits_type_properties_h
#define d4c36745_libutil_type_traits_type_properties_h

#include "type_traits_helper_classes.hpp"
#include "extra.hpp"

namespace stdx {
  // is_const: https://en.cppreference.com/w/cpp/types/is_const
  template<class T> struct is_const          : stdx::false_type {};
  template<class T> struct is_const<const T> : stdx::true_type {};

  // is_volatile: https://en.cppreference.com/w/cpp/types/is_volatile
  template<class T> struct is_volatile             : stdx::false_type {};
  template<class T> struct is_volatile<volatile T> : stdx::true_type {};

  // is_trivial: https://en.cppreference.com/w/cpp/types/is_trivial
  // TODO: write implementation!

  // is_trivially_copyable: https://en.cppreference.com/w/cpp/types/is_trivially_copyable
  // TODO: write implementation!

  // is_standard_layout: https://en.cppreference.com/w/cpp/types/is_standard_layout
  // TODO: write implementation!

  // has_unique_object_representations: https://en.cppreference.com/w/cpp/types/has_unique_object_representations
  // TODO: write implementation!

  // is_empty: https://en.cppreference.com/w/cpp/types/is_empty
  // TODO: write implementation

  // is_polymorphic: https://en.cppreference.com/w/cpp/types/is_polymorphic
  namespace detail {

  template <class T>
    stdx::true_type detect_is_polymorphic(
        decltype(dynamic_cast<const volatile void*>(static_cast<T*>(nullptr)))
    );

    template <class T>
    stdx::false_type detect_is_polymorphic(...);
  }

  template <class T>
  struct is_polymorphic : decltype(detail::detect_is_polymorphic<T>(nullptr)) {};

  // is_abstract: https://en.cppreference.com/w/cpp/types/is_abstract
  // TODO: write implementation

  // is_final: https://en.cppreference.com/w/cpp/types/is_final
  // TODO: write implementation

  // is_aggregate: https://en.cppreference.com/w/cpp/types/is_aggregate
  // TODO: write implementation

  // is_signed: https://en.cppreference.com/w/cpp/types/is_signed
  // TODO: write implementation

  // is_unsigned: https://en.cppreference.com/w/cpp/types/is_unsigned
  // TODO: write implementation

  // is_bounded_array: https://en.cppreference.com/w/cpp/types/is_bounded_array
  template<class T>
  struct is_bounded_array: stdx::false_type {};

  template<class T, stdx::size_t N>
  struct is_bounded_array<T[N]> : stdx::true_type {};

  // is_unbounded_array: https://en.cppreference.com/w/cpp/types/is_unbounded_array
  template<class T>
  struct is_unbounded_array: stdx::false_type {};

  template<class T>
  struct is_unbounded_array<T[]> : stdx::true_type {};

}

#endif // d4c36745_libutil_type_traits_type_properties_h
