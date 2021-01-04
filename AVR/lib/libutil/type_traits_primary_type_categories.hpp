#ifndef d4c36745_libutil_type_traits_primary_type_categories_h
#define d4c36745_libutil_type_traits_primary_type_categories_h

#include "extra.hpp"
#include "type_traits_helper_classes.hpp"
#include "type_traits_const_volatility.hpp"
#include "type_traits_type_relationships.hpp"

namespace stdx {
  // is_void: https://en.cppreference.com/w/cpp/types/is_void
  template< class T >
  struct is_void : stdx::is_same<void, typename stdx::remove_cv<T>::type> {};

  // is_null_pointer: https://en.cppreference.com/w/cpp/types/is_null_pointer
  template< class T >
  struct is_null_pointer : stdx::is_same<stdx::nullptr_t, typename stdx::remove_cv<T>::type> {};

  // is_integral: https://en.cppreference.com/w/cpp/types/is_integral
  namespace detail {
    template<typename T> struct is_integral_base: stdx::false_type {};

    template<> struct is_integral_base<bool>: stdx::true_type {};
    template <> struct is_integral_base <char> : stdx::true_type {};
    template <> struct is_integral_base <signed char> : stdx::true_type {};
    template <> struct is_integral_base <unsigned char> : stdx::true_type {};
    template <> struct is_integral_base <char16_t> : stdx::true_type {};
    template <> struct is_integral_base <char32_t> : stdx::true_type {};
    template <> struct is_integral_base <wchar_t> : stdx::true_type {};
    template <> struct is_integral_base <short> : stdx::true_type {};
    template <> struct is_integral_base <unsigned short> : stdx::true_type {};
    template <> struct is_integral_base <int> : stdx::true_type {};
    template <> struct is_integral_base <unsigned> : stdx::true_type {};
    template <> struct is_integral_base <long> : stdx::true_type {};
    template <> struct is_integral_base <unsigned long> : stdx::true_type {};
    template <> struct is_integral_base <long long> : stdx::true_type {};
    template <> struct is_integral_base <unsigned long long> : stdx::true_type {};
  }

  template<typename T>
  struct is_integral: detail::is_integral_base<stdx::remove_cv_t<T>> {};

  // is_floating_point; https://en.cppreference.com/w/cpp/types/is_floating_point
  template< class T >
  struct is_floating_point
       : stdx::integral_constant<
           bool,
           stdx::is_same<float, typename stdx::remove_cv<T>::type>::value  ||
           stdx::is_same<double, typename stdx::remove_cv<T>::type>::value  ||
           stdx::is_same<long double, typename stdx::remove_cv<T>::type>::value
       > {};

  // is_array: https://en.cppreference.com/w/cpp/types/is_array
  template<class T>
  struct is_array : stdx::false_type {};

  template<class T>
  struct is_array<T[]> : stdx::true_type {};

  template<class T, stdx::size_t N>
  struct is_array<T[N]> : stdx::true_type {};

  // is_enum: https://en.cppreference.com/w/cpp/types/is_enum
#ifdef __GNUC__
  template<typename _Tp>
  struct is_enum : stdx::integral_constant<bool, __is_enum(_Tp)> {};
#endif

  // is_union: https://en.cppreference.com/w/cpp/types/is_union
#ifdef __GNUC__
  template<typename _Tp>
  struct is_union : stdx::integral_constant<bool, __is_union(_Tp)> {};
#endif

  // is_class: https://en.cppreference.com/w/cpp/types/is_class
#ifdef __GNUC__
  template<typename _Tp>
  struct is_class : stdx::integral_constant<bool, __is_class(_Tp)> {};
#endif

  // is_function: https://en.cppreference.com/w/cpp/types/is_function
  // TODO: write implementation!

  // is_pointer: https://en.cppreference.com/w/cpp/types/is_pointer
  namespace detail {
    template<class T>
    struct is_pointer_helper : stdx::false_type {};

    template<class T>
    struct is_pointer_helper<T*> : stdx::true_type {};
  }

  template<class T>
  struct is_pointer : detail::is_pointer_helper< typename stdx::remove_cv<T>::type > {};

  // is_lvalue_reference: https://en.cppreference.com/w/cpp/types/is_lvalue_reference
  template<class T> struct is_lvalue_reference     : stdx::false_type {};
  template<class T> struct is_lvalue_reference<T&> : stdx::true_type {};

  // is_rvalue_reference: https://en.cppreference.com/w/cpp/types/is_rvalue_reference
  template <class T> struct is_rvalue_reference      : stdx::false_type {};
  template <class T> struct is_rvalue_reference<T&&> : stdx::true_type {};

  // is_member_object_pointer: https://en.cppreference.com/w/cpp/types/is_member_object_pointer
  // TODO: write implementation!

  // is_member_function_pointer: https://en.cppreference.com/w/cpp/types/is_member_function_pointer
  // TODO: write implementation!
}

#endif // d4c36745_libutil_type_traits_primary_type_categories_h
