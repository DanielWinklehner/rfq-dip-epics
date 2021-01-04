#ifndef d4c36745_libutil_utility_h
#define d4c36745_libutil_utility_h

#include "type_traits.hpp"

// <memory>
namespace stdx {
  template<class T>
  typename stdx::enable_if<stdx::is_object<T>::value, T*>::type
  addressof(T& arg) noexcept
  {
      return reinterpret_cast<T*>(
                 &const_cast<char&>(
                     reinterpret_cast<const volatile char&>(arg)));
  }

  template<class T>
  typename stdx::enable_if<!stdx::is_object<T>::value, T*>::type
  addressof(T& arg) noexcept
  {
      return &arg;
  }
}

// <utility>
namespace stdx {
  // declval: https://en.cppreference.com/w/cpp/utility/declval
  template <class T>
  add_rvalue_reference_t<T> declval() noexcept;

  // move: https://en.cppreference.com/w/cpp/utility/move
  template <typename T>
//#if __cplusplus < 201402L
//  typename remove_reference<T>::type&& move(T&& arg)
//#else
  constexpr remove_reference_t<T>&& move( T&& arg ) noexcept
//#endif
  {
      return static_cast<typename remove_reference<T>::type&&>(arg);
  }

  // forward: https://en.cppreference.com/w/cpp/utility/forward
  template <class T>
#if __cplusplus < 201402L
  T&& forward( typename remove_reference<T>::type& arg ) noexcept
#else
  constexpr T&& forward( remove_reference_t<T>& arg ) noexcept
#endif
  {
      return static_cast<T&&>(arg);
  }

  template <class T>
#if __cplusplus < 201402L
  T&& forward( typename remove_reference<T>::type&& arg ) noexcept
#else
  constexpr T&& forward( remove_reference_t<T>&& arg ) noexcept
#endif
  {
      return static_cast<T&&>(arg);
  }
}

#endif // d4c36745_libutil_utility_h
