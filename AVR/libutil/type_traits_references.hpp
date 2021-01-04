#ifndef d4c36745_libutil_type_traits_references_h
#define d4c36745_libutil_type_traits_references_h

#include "type_traits_helper_classes.hpp"

namespace stdx {
  // remove_reference: https://en.cppreference.com/w/cpp/types/remove_reference
  template< class T > struct remove_reference      {typedef T type;};
  template< class T > struct remove_reference<T&>  {typedef T type;};
  template< class T > struct remove_reference<T&&> {typedef T type;};

  template< class T >
  using remove_reference_t = typename remove_reference<T>::type;

  // add_l/rvalue_reference: https://en.cppreference.com/w/cpp/types/add_reference
  namespace detail {
    template <class T>
    auto try_add_lvalue_reference(int) -> type_identity<T&>;
    template <class T>
    auto try_add_lvalue_reference(...) -> type_identity<T>;

    template <class T>
    auto try_add_rvalue_reference(int) -> type_identity<T&&>;
    template <class T>
    auto try_add_rvalue_reference(...) -> type_identity<T>;
  }

  template <class T>
  struct add_lvalue_reference : decltype(detail::try_add_lvalue_reference<T>(0)) {};

  template <class T>
  struct add_rvalue_reference : decltype(detail::try_add_rvalue_reference<T>(0)) {};

  template< class T >
  using add_lvalue_reference_t = typename add_lvalue_reference<T>::type;

  template< class T >
  using add_rvalue_reference_t = typename add_rvalue_reference<T>::type;
}

#endif // d4c36745_libutil_type_traits_references_h
