# libutil

A collection of standalone C++ utilities and headers for embedded systems that do not have good C++ support, ex: C++ compilers without the C++ standard library. This library intends to bridge part of that gap, especially for instances where templates are used.

The code provided by this library is not meant to be compliant with any one version of C++, but is meant to compile for any C++11 or greater compatible compiler.

This project is not for use outside of this repository, since many of the functions chosen to be implemented or not implemented are at the discretion of what is needed by myself at the moment. In addition, some of the implementations are architecture/target specific, and may not work elsewhere.

## Includes:
- type_traits
  - Some of the functions are implemented, but many are are still missing
- new
  - Some compilers do not ship with all of C++'s new and delete features, notably placement new
- initializer_list
  - Simple implementation backed by C-style arrays
- expected
  - A non-standard implementation of std::expected with void return support
- utility
  - declval, move, forward
- functional
  - reference_wrapper


##  Attributions and License
Alot of code in this directory is generously provided by [cppreference](https://cppreference.com), licensed under the Creative Commons Attribution-Sharealike 3.0 Unported License and the GNU Free Documentation License.

Some implementations are from [hideakitai's ArxTypeTraits](https://github.com/hideakitai/ArxTypeTraits), licensed under the MIT license.
