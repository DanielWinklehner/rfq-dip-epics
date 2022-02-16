#ifndef d4c36745_libutil_expected_h
#define d4c36745_libutil_expected_h

#include "type_traits.hpp"
#include "libutil_utility.hpp"

#ifdef __AVR__
  #include <assert.h>
#else
  #include <cassert>
  #include <new>
#endif

namespace stdx {

  template <class E,
            typename = typename stdx::enable_if<stdx::is_integral<E>::value>::type >
  class unexpected {
      // Cannot initialize with 0
      E val;
  public:
      // Cannot default construct an unexpected
      unexpected() = delete;

      // Copy ctor for an unexpected
      constexpr explicit unexpected(const E& e): val(e) {}

      // Move ctor for the unexpected
      constexpr explicit unexpected(E&& e): val(stdx::move(e)) {}

      // Obtain
      constexpr const E& value() const { return val; }
  };

  namespace detail {

    // Base struct
    template<typename T, typename E, typename Enable = void>
    struct expected_vars;

    template<typename T, typename E>
    struct expected_vars<T, E, typename stdx::enable_if<stdx::is_same<T, void>::value>::type> {
        bool ok = true;
        E nay;

        // Common: Copy ctor for an unexpected
        constexpr expected_vars(const unexpected<E>& rhs)
          : ok(false), nay(stdx::move(rhs.value())) {};

        // Specialized
        constexpr expected_vars() {}
    };

    template<typename T, typename E>
    struct expected_vars<T, E, typename stdx::enable_if<!stdx::is_same<T, void>::value>::type> {
        bool ok = true;
        union { T yay; E nay; };

        // Common: Copy ctor for an unexpected
        constexpr expected_vars(const unexpected<E>& rhs)
          : ok(false), nay(stdx::move(rhs.value())) {};

        // Specialized
        constexpr expected_vars()
          : yay(T()) {}

        constexpr expected_vars(const T& rhs)
          : yay(stdx::move(rhs)) {}
    };
  } // namespace detail

  template <typename T, typename E>
  class expected : public detail::expected_vars<T,E> {
      using detail::expected_vars<T, E>::ok;
      using detail::expected_vars<T, E>::nay;

  public:
      // Default Constructor
      constexpr expected()
      : detail::expected_vars<T, E>() {}

      // Templated as U b/c T might be void type, and
      // a) You cannot construct a 'T yay' from a void type,
      // and b) SFIANE will disallow copies to void (cannot cast U to T (void) )
      template <typename U>
      constexpr expected(const U& rhs)
        : detail::expected_vars<T, E>(rhs) {}

      // Copy ctor for an unexcepted
      constexpr expected(const unexpected<E>& rhs)
        : detail::expected_vars<T, E>(stdx::move(rhs)) {};

      // Copy ctor for a non-void expected
      template <typename U = T> // T is same to U is implicit via the enable_if_t<cond(U), T> in the fn argspec
      constexpr expected(const expected<stdx::enable_if_t<!stdx::is_void<U>::value, T>, E>& rhs)
        : detail::expected_vars<T, E>::yay(rhs.ok ? rhs.yay : T()),
          detail::expected_vars<T, E>::nay(rhs.ok ? nay : rhs.nay)
      {}

      // Copy ctor for a void expected
      template <typename U = T>
      constexpr expected(const expected<stdx::enable_if_t<stdx::is_void<U>::value, T>, E>& rhs)
        : detail::expected_vars<T, E>::nay(rhs.ok ? E() : rhs.nay)
      {}

      // Move ctor for a non-void expected
      template <typename U = T>
      constexpr expected(const expected<stdx::enable_if_t<!stdx::is_void<U>::value, T>, E>&& rhs)
        : detail::expected_vars<T, E>::yay(rhs.ok ? stdx::move(rhs.yay) : T()),
          detail::expected_vars<T, E>::nay(rhs.ok ? nay : stdx::move(rhs.nay))
      {}

      // Move ctor for a void expected
      // move an expected into here, if the expected is a void type
      template <typename U = T>
      constexpr expected(const expected<stdx::enable_if_t<stdx::is_void<U>::value, T>, E>&& rhs)
        : detail::expected_vars<T, E>::nay(rhs.ok ? E() : stdx::move(rhs.nay))
      {}

      // Boolean operator for determining if return value is valid or an error
      constexpr explicit operator bool() const { return ok; }


      // "Safer" operation for retriving value
      template <typename U = T>
      constexpr const stdx::enable_if_t<!stdx::is_void<U>::value, T>& value() const
      { return (assert(ok), this->yay); }

      template <typename U = T>
  #if __cplusplus >= 201402L
      constexpr
  #endif
      stdx::enable_if_t<!stdx::is_void<U>::value, T>& value()
      { return (assert(ok), this->yay); }


      // "Dangerous" operation for retriving value
      template <typename U = T>
      constexpr const stdx::enable_if_t<!stdx::is_void<U>::value, T>& operator*() const
      { return this->yay; }

      template <typename U = T>
  #if __cplusplus >= 201402L
      constexpr
  #endif
      stdx::enable_if_t<!stdx::is_void<U>::value, T>& operator*()
      { return this->yay; }


      // Get the error
      constexpr const E& error() const
      { return (assert(!ok), nay); }

  #if __cplusplus >= 201402L
      constexpr
  #endif
      E& error()
      { return (assert(!ok), nay); }
  };

} // namespace stdx

#endif // d4c36745_libutil_expected_h
