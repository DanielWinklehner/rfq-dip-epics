#ifndef d4c36745_libutil_type_traits_pointers_h
#define d4c36745_libutil_type_traits_pointers_h

#include "type_traits_helper_classes.hpp"
#include "type_traits_references.hpp"

namespace stdx {
  // remove_pointer: https://en.cppreference.com/w/cpp/types/remove_pointer
  template< class T > struct remove_pointer                    {typedef T type;};
  template< class T > struct remove_pointer<T*>                {typedef T type;};
  template< class T > struct remove_pointer<T* const>          {typedef T type;};
  template< class T > struct remove_pointer<T* volatile>       {typedef T type;};
  template< class T > struct remove_pointer<T* const volatile> {typedef T type;};

  template< class T >
  using remove_pointer_t = typename remove_pointer<T>::type;

  // add_pointer: https://en.cppreference.com/w/cpp/types/add_pointer
  namespace detail {
    template <class T>
    auto try_add_pointer(int) -> type_identity<typename stdx::remove_reference<T>::type*>;

    template <class T>
    auto try_add_pointer(...) -> type_identity<T>;
  }

  template <class T>
  struct add_pointer : decltype(detail::try_add_pointer<T>(0)) {};

  template< class T >
  using add_pointer_t = typename add_pointer<T>::type;
}

#endif // d4c36745_libutil_type_traits_pointers_h
