#ifndef d4c36745_libutil_type_traits_composite_type_categories_h
#define d4c36745_libutil_type_traits_composite_type_categories_h

#include "type_traits_helper_classes.hpp"
#include "type_traits_primary_type_categories.hpp"

namespace stdx {
  // Forward declare:
  template<class T> struct is_member_pointer;

  // is_fundamental: https://en.cppreference.com/w/cpp/types/is_fundamental
  // TODO: write implementation!

  // is_arithmetic: https://en.cppreference.com/w/cpp/types/is_arithmetic
  template< class T >
  struct is_arithmetic : stdx::integral_constant<bool,
                                                stdx::is_integral<T>::value ||
                                                stdx::is_floating_point<T>::value> {};

  // is_scalar: https://en.cppreference.com/w/cpp/types/is_scalar
  template< class T >
  struct is_scalar : stdx::integral_constant<bool,
                       stdx::is_arithmetic<T>::value     ||
                       stdx::is_enum<T>::value           ||
                       stdx::is_pointer<T>::value        ||
                       stdx::is_member_pointer<T>::value ||
                       stdx::is_null_pointer<T>::value> {};

  // is_object: https://en.cppreference.com/w/cpp/types/is_object
  template< class T>
  struct is_object : stdx::integral_constant<bool,
                       stdx::is_scalar<T>::value ||
                       stdx::is_array<T>::value  ||
                       stdx::is_union<T>::value  ||
                       stdx::is_class<T>::value> {};

  // is_compound: https://en.cppreference.com/w/cpp/types/is_compound
  // template< class T >
  // struct is_compound : stdx::integral_constant<bool, !stdx::is_fundamental<T>::value> {};

  // is_reference: https://en.cppreference.com/w/cpp/types/is_reference
  template <class T> struct is_reference      : stdx::false_type {};
  template <class T> struct is_reference<T&>  : stdx::true_type {};
  template <class T> struct is_reference<T&&> : stdx::true_type {};

  // is_member_pointer: https://en.cppreference.com/w/cpp/types/is_member_pointer
  template<class T>
  struct is_member_pointer_helper : stdx::false_type {};

  template<class T, class U>
  struct is_member_pointer_helper<T U::*> : stdx::true_type {};

  template<class T>
  struct is_member_pointer :
      is_member_pointer_helper<typename stdx::remove_cv<T>::type> {};
}

#endif // d4c36745_libutil_type_traits_composite_type_categories_h
