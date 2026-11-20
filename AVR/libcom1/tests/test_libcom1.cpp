// Unit tests for libcom1. Runs on a PC, see the Makefile.
//
// Built twice: with snprintf("%g") formatting (what Teensy, Opta and other non-AVR boards use)
// and with -DLIBCOM1_USE_DTOSTRE=1 (what Arduino AVR boards use, via a dtostre stand-in).

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <vector>

#if LIBCOM1_USE_DTOSTRE
#include "dtostre_shim.hpp"
#endif

#include <libcom1.hpp>

// ---------------------------------------------------------------------------------------------
// Tiny test framework
// ---------------------------------------------------------------------------------------------
static int g_checks = 0;
static int g_failed = 0;

#define CHECK(cond)                                                                   \
  do {                                                                                \
    ++g_checks;                                                                       \
    if (!(cond)) {                                                                    \
      ++g_failed;                                                                     \
      printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                          \
    }                                                                                 \
  } while (0)

#define CHECK_STR(actual, expected)                                                   \
  do {                                                                                \
    ++g_checks;                                                                       \
    const std::string a_ = (actual);                                                  \
    const std::string e_ = (expected);                                                \
    if (a_ != e_) {                                                                   \
      ++g_failed;                                                                     \
      printf("FAIL %s:%d: got \"%s\", expected \"%s\"\n", __FILE__, __LINE__,         \
             a_.c_str(), e_.c_str());                                                 \
    }                                                                                 \
  } while (0)

#define CHECK_NEAR(actual, expected)                                                  \
  do {                                                                                \
    ++g_checks;                                                                       \
    const double a_ = (actual);                                                       \
    const double e_ = (expected);                                                     \
    if (!(std::fabs(a_ - e_) <= 1e-5 * std::fabs(e_) + 1e-30)) {                      \
      ++g_failed;                                                                     \
      printf("FAIL %s:%d: got %.9g, expected %.9g\n", __FILE__, __LINE__, a_, e_);    \
    }                                                                                 \
  } while (0)

// Text of one value the way this build formats it
static std::string fmt(float v)
{
  char buf[32];
  mist1::com1::detail::format_value(v, buf);
  return buf;
}

// "o1:2:3" -> {1, 2, 3}. `prefix` characters are skipped first.
static std::vector<double> fields(const std::string& reply, size_t prefix = 1)
{
  std::vector<double> out;
  size_t pos = prefix;
  while (pos <= reply.size()) {
    size_t colon = reply.find(':', pos);
    if (colon == std::string::npos)
      colon = reply.size();
    out.push_back(std::strtod(reply.substr(pos, colon - pos).c_str(), nullptr));
    pos = colon + 1;
  }
  return out;
}

// ---------------------------------------------------------------------------------------------
// Fake serial port, read the way the sketches do it (LineBuffer, non-blocking)
// ---------------------------------------------------------------------------------------------
static std::deque<char> g_rx_bytes;
static std::vector<std::string> g_tx_lines;
static mist1::com1::LineBuffer<32> g_rx;

static char* serial_read()
{
  while (!g_rx_bytes.empty()) {
    const char c = g_rx_bytes.front();
    g_rx_bytes.pop_front();
    if (g_rx.feed(c))
      return g_rx.take();
  }
  return g_rx.none();
}

static void serial_write(char* str) { g_tx_lines.push_back(str); }

static void push(const char* bytes)
{
  for (; *bytes != '\0'; ++bytes)
  { g_rx_bytes.push_back(*bytes); }
}

// ---------------------------------------------------------------------------------------------
// Devices under test
// ---------------------------------------------------------------------------------------------
using mist1::com1::Channel;
using mist1::com1::IndexedChannel;

static float g_v[12];
static float g_set_a = -999.0f;
static float g_set_w = -999.0f;
static int g_set_calls = 0;
static float g_idx[4] = { 10.0f, 20.0f, 30.0f, 40.0f };
static int g_timeout_calls = 0;

#define GETTER(n) static float get_v##n() { return g_v[n]; }
GETTER(0) GETTER(1) GETTER(2) GETTER(3) GETTER(4) GETTER(5)
GETTER(6) GETTER(7) GETTER(8) GETTER(9) GETTER(10) GETTER(11)

static void set_a(float v) { g_set_a = v; g_v[0] = v; ++g_set_calls; }
static void set_w(float v) { g_set_w = v; ++g_set_calls; }
static float get_idx(uint8_t i) { return g_idx[i]; }
static void set_idx(uint8_t i, float v) { g_idx[i] = v; }
static void on_timeout() { ++g_timeout_calls; }

// 12 plain channels in the smallest buffer the library accepts for them
MakeChannelMap(map12, 12, ({
    Channel{ 't', 1, &get_v0, nullptr }, Channel{ 't', 2, &get_v1, nullptr },
    Channel{ 't', 3, &get_v2, nullptr }, Channel{ 't', 4, &get_v3, nullptr },
    Channel{ 't', 5, &get_v4, nullptr }, Channel{ 't', 6, &get_v5, nullptr },
    Channel{ 't', 7, &get_v6, nullptr }, Channel{ 'f', 1, &get_v7, nullptr },
    Channel{ 'f', 2, &get_v8, nullptr }, Channel{ 'f', 3, &get_v9, nullptr },
    Channel{ 'f', 4, &get_v10, nullptr }, Channel{ 'f', 5, &get_v11, nullptr },
  })
);
static constexpr size_t BUF12 = mist1::com1::min_out_buffer_size(12);
static mist1::com1::IOHandler<BUF12> io12(serial_read, serial_write);
static mist1::com1::SerialDevice<BUF12, 12> dev12(io12, map12);

// Mixed channel kinds: read/write, read-only, write-only, indexed
MakeChannelMap(map_mixed, 5, ({
    Channel{ 'a', 1, &get_v0, &set_a },
    Channel{ 'r', 1, &get_v1, nullptr },
    Channel{ 'w', 1, nullptr, &set_w },
    IndexedChannel('x', 1, &get_idx, &set_idx, 2),
    IndexedChannel('x', 2, &get_idx, nullptr, 3),
  })
);
static mist1::com1::IOHandler<128> io_mixed(serial_read, serial_write);
static mist1::com1::SerialDevice<128, 5> dev(io_mixed, map_mixed);

// One channel in the minimum buffer: too small for identity and streaming
MakeChannelMap(map_tiny, 1, ({ Channel{ 'a', 1, &get_v0, &set_a } }));
static mist1::com1::IOHandler<16> io_tiny(serial_read, serial_write);
static mist1::com1::SerialDevice<16, 1> dev_tiny(io_tiny, map_tiny);

// Send raw bytes, let the device process every complete line, return its replies joined by '|'
template <typename Device>
static std::string talk(Device& device, const char* bytes)
{
  g_tx_lines.clear();
  push(bytes);
  do {
    device.communicate();
  } while (!g_rx_bytes.empty());

  std::string joined;
  for (size_t i = 0; i < g_tx_lines.size(); ++i) {
    if (i != 0)
      joined += '|';
    joined += g_tx_lines[i];
  }
  return joined;
}

template <typename Device>
static std::string tick(Device& device, uint32_t now_ms, const char* bytes = "")
{
  g_tx_lines.clear();
  push(bytes);
  device.service(now_ms);
  std::string joined;
  for (size_t i = 0; i < g_tx_lines.size(); ++i) {
    if (i != 0)
      joined += '|';
    joined += g_tx_lines[i];
  }
  return joined;
}

// ---------------------------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------------------------
static void test_line_buffer()
{
  mist1::com1::LineBuffer<8> lb;

  // No line until '\n'
  CHECK(!lb.feed('A'));
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "A");

  // CR LF and LF are both accepted, empty lines are ignored
  CHECK(!lb.feed('\r'));
  CHECK(!lb.feed('\n'));
  for (const char* c = "ga1\r"; *c; ++c) CHECK(!lb.feed(*c));
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "ga1");

  // A shorter line after a longer one carries nothing over
  for (const char* c = "sa1100"; *c; ++c) lb.feed(*c);
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "sa1100");
  for (const char* c = "sa15"; *c; ++c) lb.feed(*c);
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "sa15");

  // Exactly N - 1 characters fit
  for (const char* c = "1234567"; *c; ++c) CHECK(!lb.feed(*c));
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "1234567");

  // One more does not: the whole line is dropped and reported as "!"
  for (const char* c = "sa199999999999"; *c; ++c) CHECK(!lb.feed(*c));
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "!");

  // ... and the next line is unaffected
  for (const char* c = "A"; *c; ++c) lb.feed(*c);
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "A");

  CHECK_STR(lb.none(), "");

  // reset() forgets a partial line
  lb.feed('s'); lb.feed('a');
  lb.reset();
  lb.feed('A');
  CHECK(lb.feed('\n'));
  CHECK_STR(lb.take(), "A");
}

static void test_stale_buffer_regression()
{
  // Bug: "sa1100" followed by "sa15" set 500, "sa1-5" followed by "sa15" set 55.
  talk(dev, "sa1100\n");
  CHECK_NEAR(g_set_a, 100.0);
  talk(dev, "sa15\n");
  CHECK_NEAR(g_set_a, 5.0);
  talk(dev, "sa1-5\n");
  CHECK_NEAR(g_set_a, -5.0);
  talk(dev, "sa15\n");
  CHECK_NEAR(g_set_a, 5.0);

  // Two commands arriving in one chunk are both processed, in order
  talk(dev, "sa11\nsa12\n");
  CHECK_NEAR(g_set_a, 2.0);

  // A partial line does nothing and produces no reply
  CHECK_STR(talk(dev, "sa17"), "");
  CHECK_NEAR(g_set_a, 2.0);
  CHECK_STR(talk(dev, "7\n"), "");
  CHECK_NEAR(g_set_a, 77.0);
}

static void test_query_all()
{
  for (int i = 0; i < 12; ++i) g_v[i] = 1.5f * (i + 1);
  std::string reply = talk(dev12, "A\n");
  CHECK(reply[0] == 'o');
  std::vector<double> v = fields(reply);
  CHECK(v.size() == 12);
  for (size_t i = 0; i < v.size() && i < 12; ++i) CHECK_NEAR(v[i], 1.5 * (i + 1));

#if LIBCOM1_USE_DTOSTRE
  CHECK_STR(reply.substr(0, 19), "o+1.5e+00:+3.e+00:+");
#else
  CHECK_STR(reply.substr(0, 9), "o1.5:3:4.");
#endif

  // Values recorded from a sensor box: this reply needs 145 bytes on AVR and used to
  // overflow the 128 byte buffer.
  const float sensor_box[12] = { 23.4609375f, 24.1171875f, 22.9921875f, 31.5078125f, 28.3359375f,
                                 45.6640625f, 23.0546875f, 1.26f, 0.0f, 2.34f, 0.0f, 1.02f };
  for (int i = 0; i < 12; ++i) g_v[i] = sensor_box[i];
  reply = talk(dev12, "A\n");
  v = fields(reply);
  CHECK(v.size() == 12);
  for (size_t i = 0; i < v.size() && i < 12; ++i)
    CHECK(std::fabs(v[i] - sensor_box[i]) <= 1e-4 * std::fabs(sensor_box[i]) + 1e-9);
}

static void test_query_all_worst_case_fits()
{
  // Longest possible text for every channel, in the smallest buffer SerialDevice accepts.
  // The sanitizers abort the test on any write outside the buffer.
  const float worst[] = { -1.234567e-5f, -3.402823e38f, 1.175494e-38f, -9.999999e-10f };
  for (float w : worst) {
    for (int i = 0; i < 12; ++i) g_v[i] = w;
    const std::string reply = talk(dev12, "A\n");
    CHECK(reply.size() < BUF12);
    const std::vector<double> v = fields(reply);
    CHECK(v.size() == 12);
    for (double x : v) CHECK(std::fabs(x - w) <= 1e-5 * std::fabs(w));
    CHECK(fmt(w).size() <= mist1::com1::detail::MAX_VALUE_CHARS);
  }
}

static void test_non_finite_values()
{
  // Bug: on Arduino AVR a NaN cut the reply off, every channel after it was lost.
  for (int i = 0; i < 12; ++i) g_v[i] = static_cast<float>(i);
  g_v[1] = NAN;
  g_v[5] = INFINITY;
  g_v[6] = -INFINITY;
  const std::string reply = talk(dev12, "A\n");
  const std::vector<double> v = fields(reply);
  CHECK(v.size() == 12);
  if (v.size() == 12) {
    CHECK(std::isnan(v[1]));
    CHECK(std::isinf(v[5]) && v[5] > 0);
    CHECK(std::isinf(v[6]) && v[6] < 0);
    CHECK_NEAR(v[0], 0.0);
    CHECK_NEAR(v[2], 2.0);
    CHECK_NEAR(v[11], 11.0);
  }
  CHECK(reply.find(":nan:") != std::string::npos);
  CHECK(reply.find(":inf:-inf:") != std::string::npos);
}

static void test_set_commands()
{
  g_set_calls = 0;

  // 's' has no reply on success, 'S' acknowledges
  CHECK_STR(talk(dev, "sa13.25\n"), "");
  CHECK_NEAR(g_set_a, 3.25);
  CHECK_STR(talk(dev, "Sa1-7.5\n"), "ok");
  CHECK_NEAR(g_set_a, -7.5);
  CHECK_STR(talk(dev, "Sa11e3\n"), "ok");
  CHECK_NEAR(g_set_a, 1000.0);
  CHECK_STR(talk(dev, "Sa12.5 \r\n"), "ok");
  CHECK_NEAR(g_set_a, 2.5);
  CHECK_STR(talk(dev, "Sw10.5\n"), "ok");
  CHECK_NEAR(g_set_w, 0.5);
  CHECK(g_set_calls == 5);

  // Malformed values are rejected and the setter is not called (atof() used to turn them into 0)
  const float before = g_set_a;
  CHECK_STR(talk(dev, "Sa1\n"), "ERR5");
  CHECK_STR(talk(dev, "sa1\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa1abc\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa11.5x\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa11.5 2\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa1nan\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa1inf\n"), "ERR5");
  CHECK_STR(talk(dev, "Sa11e99\n"), "ERR5");
  CHECK_STR(talk(dev, "S\n"), "ERR5");
  CHECK(g_set_calls == 5);
  CHECK_NEAR(g_set_a, before);

  // Unknown channel, read-only channel
  CHECK_STR(talk(dev, "Sz11\n"), "ERR4");
  CHECK_STR(talk(dev, "Sr11\n"), "ERR7");
  CHECK_STR(talk(dev, "Sx21\n"), "ERR7");
  CHECK(g_set_calls == 5);

  // A line that is too long is never executed, not even truncated
  CHECK_STR(talk(dev, "Sa11.00000000000000000000000000000000000000001\n"), "ERR0");
  CHECK(g_set_calls == 5);
}

static void test_plain_query()
{
  g_v[0] = 4091.71f;
  g_v[1] = 1.5e-12f;
  CHECK_STR(talk(dev, "ga1\n"), "o" + fmt(4091.71f));
  CHECK_NEAR(fields(talk(dev, "ga1\n"))[0], 4091.71);
  CHECK_NEAR(fields(talk(dev, "gr1\n"))[0], 1.5e-12);   // no exponent limit
  g_v[1] = 2.5e10f;
  CHECK_NEAR(fields(talk(dev, "gr1\n"))[0], 2.5e10);
  g_v[1] = NAN;
  CHECK_STR(talk(dev, "gr1\n"), "onan");

  CHECK_STR(talk(dev, "gz9\n"), "ERR4");
  CHECK_STR(talk(dev, "gw1\n"), "ERR7");   // write-only
  CHECK_STR(talk(dev, "ga\n"), "ERR5");
  CHECK_STR(talk(dev, "g\n"), "ERR5");
}

static void test_legacy_single_query()
{
  // Same replies as the original implementation for representable values
  g_v[0] = 4091.71f;
  CHECK_STR(talk(dev, "q01a13\n"), "oa1+40923+");
  CHECK_STR(talk(dev, "q01a16\n"), "oa1+40917103+");
  CHECK_STR(talk(dev, "q01a10\n"), "oa1+43+");
  g_v[0] = 1.5e-7f;
  CHECK_STR(talk(dev, "q01a13\n"), "oa1+15007-");
  g_v[0] = -0.31f;
  CHECK_STR(talk(dev, "q01a12\n"), "oa1-3101-");
  g_v[0] = 0.0f;
  CHECK_STR(talk(dev, "q01a12\n"), "oa1+0000+");
  g_v[0] = 9.99e9f;
  CHECK_STR(talk(dev, "q01a12\n"), "oa1+9999+");

  // Bug: exponents of two digits lost their leading digit (1.5e-12 was sent as 1.5e-2)
  g_v[0] = 1.5e-12f;
  CHECK_STR(talk(dev, "q01a13\n"), "ERR6");
  g_v[0] = 2.5e10f;
  CHECK_STR(talk(dev, "q01a13\n"), "ERR6");
  g_v[0] = 9.9999e9f;                       // rounds up to 1.00e10 at this precision
  CHECK_STR(talk(dev, "q01a12\n"), "ERR6");
  g_v[0] = NAN;
  CHECK_STR(talk(dev, "q01a13\n"), "ERR6");
  g_v[0] = INFINITY;
  CHECK_STR(talk(dev, "q01a13\n"), "ERR6");

  g_v[0] = 1.0f;
  CHECK_STR(talk(dev, "q01a17\n"), "ERR1");
  CHECK_STR(talk(dev, "q05a13\n"), "ERR3");
  CHECK_STR(talk(dev, "q01z93\n"), "ERR4");
  CHECK_STR(talk(dev, "q01w13\n"), "ERR7");
  CHECK_STR(talk(dev, "q01a1\n"), "ERR5");
  CHECK_STR(talk(dev, "q\n"), "ERR5");
}

static void test_channel_kinds()
{
  g_v[0] = 1.0f;
  g_v[1] = 2.0f;
  g_idx[2] = 30.0f;
  g_idx[3] = 40.0f;

  // Write-only channels keep their position and read as 0
  std::vector<double> v = fields(talk(dev, "A\n"));
  CHECK(v.size() == 5);
  if (v.size() == 5) {
    CHECK_NEAR(v[0], 1.0);
    CHECK_NEAR(v[1], 2.0);
    CHECK_NEAR(v[2], 0.0);
    CHECK_NEAR(v[3], 30.0);
    CHECK_NEAR(v[4], 40.0);
  }

  // Indexed callbacks get the channel's argument
  CHECK_STR(talk(dev, "Sx155\n"), "ok");
  CHECK_NEAR(g_idx[2], 55.0);
  CHECK_NEAR(g_idx[3], 40.0);
  CHECK_NEAR(fields(talk(dev, "gx1\n"))[0], 55.0);
  CHECK_NEAR(fields(talk(dev, "gx2\n"))[0], 40.0);
}

static void test_identity()
{
  CHECK_STR(talk(dev, "I\n"), "oID=libcom1;FW=0;PROTO=2;CH=a1,r1,w1,x1,x2");
  dev.set_identity("SolenoidValveBox", "2.0");
  CHECK_STR(talk(dev, "I\n"), "oID=SolenoidValveBox;FW=2.0;PROTO=2;CH=a1,r1,w1,x1,x2");
  dev.set_identity("libcom1", "0");

  CHECK_STR(talk(dev12, "I\n"), "oID=libcom1;FW=0;PROTO=2;CH=t1,t2,t3,t4,t5,t6,t7,f1,f2,f3,f4,f5");

  // Does not fit a 16 byte buffer: an error, not an overflow
  CHECK_STR(talk(dev_tiny, "I\n"), "ERR2");
}

static void test_unknown_and_empty()
{
  CHECK_STR(talk(dev, "?\n"), "ERR0");
  CHECK_STR(talk(dev, "hello\n"), "ERR0");
  CHECK_STR(talk(dev, "\n"), "");
  CHECK_STR(talk(dev, "\r\n\r\n"), "");
  CHECK(dev.communicate() == mist1::com1::ERR_NO_DATA);
}

static void test_streaming()
{
  g_v[0] = 1.0f; g_v[1] = 2.0f; g_idx[2] = 3.0f; g_idx[3] = 4.0f;
  const std::string values = fmt(1.0f) + ":" + fmt(2.0f) + ":" + fmt(0.0f) + ":" + fmt(3.0f) + ":" + fmt(4.0f);

  // Off by default
  CHECK_STR(tick(dev, 1000), "");
  CHECK_STR(tick(dev, 5000), "");

  // First frame one period after the command, then one per period, numbered
  CHECK_STR(tick(dev, 5000, "P100\n"), "ok");
  CHECK(dev.stream_period() == 100);
  CHECK_STR(tick(dev, 5050), "");
  CHECK_STR(tick(dev, 5099), "");
  CHECK_STR(tick(dev, 5100), "t0:5100:" + values);
  CHECK_STR(tick(dev, 5101), "");
  CHECK_STR(tick(dev, 5199), "");
  CHECK_STR(tick(dev, 5203), "t1:5203:" + values);
  CHECK_STR(tick(dev, 5299), "");
  CHECK_STR(tick(dev, 5300), "t2:5300:" + values);   // schedule does not drift after a late frame

  // A slow loop does not cause a burst
  CHECK_STR(tick(dev, 6000), "t3:6000:" + values);
  CHECK_STR(tick(dev, 6001), "");
  CHECK_STR(tick(dev, 6099), "");
  CHECK_STR(tick(dev, 6100), "t4:6100:" + values);

  // Commands are still answered while streaming
  CHECK_STR(tick(dev, 6150, "ga1\n"), "o" + fmt(1.0f));

  // Off
  CHECK_STR(tick(dev, 6160, "P0\n"), "ok");
  CHECK_STR(tick(dev, 6500), "");
  CHECK(dev.stream_period() == 0);

  // Across the 32 bit millisecond wrap
  CHECK_STR(tick(dev, 0xFFFFFFC0u, "P100\n"), "ok");
  CHECK_STR(tick(dev, 0xFFFFFFF0u), "");
  CHECK_STR(tick(dev, 0x00000023u), "");
  CHECK(tick(dev, 0x00000024u).substr(0, 6) == "t5:36:");
  CHECK_STR(tick(dev, 0x00000030u, "P0\n"), "ok");

  // Bad arguments
  CHECK_STR(tick(dev, 100, "P\n"), "ERR5");
  CHECK_STR(tick(dev, 100, "Pabc\n"), "ERR5");
  CHECK_STR(tick(dev, 100, "P-5\n"), "ERR5");
  CHECK_STR(tick(dev, 100, "P10x\n"), "ERR5");
  CHECK(dev.stream_period() == 0);

  // A frame would not fit the 16 byte buffer: refused, streaming stays off
  CHECK_STR(tick(dev_tiny, 100, "P100\n"), "ERR2");
  CHECK(!dev_tiny.set_stream_period(100));
  CHECK(dev_tiny.stream_period() == 0);
  CHECK_STR(tick(dev_tiny, 1000), "");

  // The 12 channel device in its minimum buffer cannot stream either
  CHECK(BUF12 < mist1::com1::min_stream_buffer_size(12));
  CHECK_STR(tick(dev12, 100, "P100\n"), "ERR2");
}

static void test_comm_timeout()
{
  g_timeout_calls = 0;
  dev.set_comm_timeout(500, &on_timeout);

  CHECK_STR(tick(dev, 10000, "ga1\n").substr(0, 1), "o");
  tick(dev, 10499);
  CHECK(g_timeout_calls == 0);
  CHECK(!dev.comm_lost());

  // Fires once
  tick(dev, 10500);
  CHECK(g_timeout_calls == 1);
  CHECK(dev.comm_lost());
  tick(dev, 12000);
  CHECK(g_timeout_calls == 1);

  // Garbage does not count as a sign of life
  CHECK_STR(tick(dev, 12001, "?\n"), "ERR0");
  CHECK(dev.comm_lost());

  // A valid command does, and re-arms the timeout
  tick(dev, 12002, "A\n");
  CHECK(!dev.comm_lost());
  tick(dev, 12501);
  CHECK(g_timeout_calls == 1);
  tick(dev, 12502);
  CHECK(g_timeout_calls == 2);

  // Across the millisecond wrap
  tick(dev, 0xFFFFFF00u, "A\n");
  CHECK(!dev.comm_lost());
  tick(dev, 0x000000F3u);
  CHECK(g_timeout_calls == 2);
  tick(dev, 0x000000F4u);
  CHECK(g_timeout_calls == 3);

  // Disabled
  dev.set_comm_timeout(0, nullptr);
  CHECK(!dev.comm_lost());
  tick(dev, 0x10000000u);
  CHECK(g_timeout_calls == 3);
}

static void test_legacy_intr_communicate()
{
  g_v[0] = 1.0f; g_v[1] = 2.0f; g_idx[2] = 3.0f; g_idx[3] = 4.0f;
  g_tx_lines.clear();
  dev.intr_communicate();     // no input: sends all channels
  CHECK(g_tx_lines.size() == 1);
  if (!g_tx_lines.empty())
    CHECK(fields(g_tx_lines[0]).size() == 5);

  g_tx_lines.clear();
  push("sa19\n");
  dev.intr_communicate();
  CHECK(g_tx_lines.empty());
  CHECK_NEAR(g_set_a, 9.0);
}

static void test_buffer_size_helpers()
{
  static_assert(mist1::com1::min_out_buffer_size(1) == 16, "");
  static_assert(mist1::com1::min_out_buffer_size(9) == 128, "");
  static_assert(mist1::com1::min_out_buffer_size(12) == 170, "");
  static_assert(mist1::com1::min_stream_buffer_size(12) == 187, "");
  CHECK(true);
}

int main()
{
  test_line_buffer();
  test_stale_buffer_regression();
  test_query_all();
  test_query_all_worst_case_fits();
  test_non_finite_values();
  test_set_commands();
  test_plain_query();
  test_legacy_single_query();
  test_channel_kinds();
  test_identity();
  test_unknown_and_empty();
  test_streaming();
  test_comm_timeout();
  test_legacy_intr_communicate();
  test_buffer_size_helpers();

  printf("%s formatting: %d checks, %d failed\n",
         LIBCOM1_USE_DTOSTRE ? "dtostre" : "snprintf", g_checks, g_failed);
  return g_failed == 0 ? 0 : 1;
}
