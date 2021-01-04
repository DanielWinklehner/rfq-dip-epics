#ifndef d4c36745_libutil_type_traits_misc_transformations_h
#define d4c36745_libutil_type_traits_misc_transformations_h

#include "type_traits_helper_classes.hpp"
#include "type_traits_references.hpp"
#include "type_traits_const_volatility.hpp"

namespace stdx {
  // aligned_storage: https://en.cppreference.com/w/cpp/types/aligned_storage
  // TODO: write implementation

  // aligned_union: https://en.cppreference.com/w/cpp/types/aligned_union
  // TODO: write implementation

  // decay: https://en.cppreference.com/w/cpp/types/decay
  // TODO: write implementation

  // remove_cvref: https://en.cppreference.com/w/cpp/types/remove_cvref
  template< class T >
  struct remove_cvref {
      typedef stdx::remove_cv_t<stdx::remove_reference_t<T>> type;
  };

  template< class T >
  using remove_cvref_t = typename remove_cvref<T>::type;

  // enable_if: https://en.cppreference.com/w/cpp/types/enable_if
  template<bool B, class T = void>
  struct enable_if {};

  template<class T>
  struct enable_if<true, T> { typedef T type; };

  template< bool B, class T = void >
  using enable_if_t = typename enable_if<B,T>::type;

  // conditional: https://en.cppreference.com/w/cpp/types/conditional
  template<bool B, class T, class F>
  struct conditional { typedef T type; };

  template<class T, class F>
  struct conditional<false, T, F> { typedef F type; };

  template< bool B, class T, class F >
  using conditional_t = typename conditional<B,T,F>::type;

  // common_type: https://en.cppreference.com/w/cpp/types/common_type
  // TODO: write implementation

  // underlying_type: https://en.cppreference.com/w/cpp/types/underlying_type
  // TODO: write implementation

  // invoke_result: https://en.cppreference.com/w/cpp/types/result_of
  // TODO: write implementation

  // void_t: https://en.cppreference.com/w/cpp/types/void_t
  template< class... >
  using void_t = void;

  // conjunction: https://en.cppreference.com/w/cpp/types/conjunction
  // TODO: write implementation

  // disjunction: https://en.cppreference.com/w/cpp/types/disjunction
  // TODO: write implementation

  // negation: https://en.cppreference.com/w/cpp/types/negation
  template<class B>
  struct negation : stdx::bool_constant<!bool(B::value)> { };
}

#endif // d4c36745_libutil_type_traits_misc_transformations_h
