// Adapted from
// https://github.com/hideakitai/ArxTypeTraits/blob/master/ArxTypeTraits/initializer_list.h

#ifndef d4c36745_libutil_initializer_list_h
#define d4c36745_libutil_initializer_list_h

#if __has_include(<initializer_list>)
#include <initializer_list>
#else

#include "extra.h"

namespace stdx {

  template<class T>
  class initializer_list
  {
  private:
      const T* array;
      size_t length;

#if __cplusplus >= 201402L
      constexpr
#endif
      initializer_list(const T* a, size_t l) noexcept
        : array(a), length(l) {}
      
  public:
            
      typedef T        value_type;
      typedef const T& reference;
      typedef const T& const_reference;
      typedef size_t    size_type;
      
      typedef const T* iterator;
      typedef const T* const_iterator;

#if __cplusplus >= 201402L
      constexpr
#endif
      initializer_list() noexcept : array(nullptr), length(0) {}
      
#if __cplusplus >= 201402L
      constexpr
#endif
      size_t size() const noexcept { return length; }
      
#if __cplusplus >= 201402L
      constexpr
#endif
      const T* begin() const { return array; }
      
#if __cplusplus >= 201402L
      constexpr
#endif
      const T* end() const { return array + length; }
  };

} // namespace stdx

#endif

#endif // d4c36745_libutil_initializer_list_h
