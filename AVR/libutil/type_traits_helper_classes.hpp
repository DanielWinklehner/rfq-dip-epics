#ifndef d4c36745_libutil_type_traits_helper_classes_h
#define d4c36745_libutil_type_traits_helper_classes_h

namespace stdx {
  // integral_constant: https://en.cppreference.com/w/cpp/types/integral_constant
  template<class T, T v>
  struct integral_constant {
      static constexpr T value = v;
      using value_type = T;
      using type = integral_constant; // using injected-class-name
      constexpr operator value_type() const noexcept { return value; }
      constexpr value_type operator()() const noexcept { return value; } //since c++14
  };

  template <bool B>
  using bool_constant = integral_constant<bool, B>;

  using true_type = stdx::integral_constant<bool, true>;
  using false_type = stdx::integral_constant<bool, false>;

  // type_identity: https://en.cppreference.com/w/cpp/types/type_identity
  template< class T >
  struct type_identity {
      using type = T;
  };

  template< class T >
  using type_identity_t = typename type_identity<T>::type;
}

#endif // d4c36745_libutil_type_traits_helper_classes_h
