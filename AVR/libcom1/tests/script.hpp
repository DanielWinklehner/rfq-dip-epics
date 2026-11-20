#ifndef libcom1_tests_script_h
#define libcom1_tests_script_h

// A fixed conversation with a libcom1 device, shared by
//  - replay_host.cpp   (PC, dtostre stand-in)
//  - avr_sim/sim_main.cpp (ATmega2560 in simavr, real avr-libc)
// Both print every reply; `make avr-sim` diffs the two outputs.
//
// The including file must provide:  static void emit(const char* line);

#include <libcom1.hpp>

namespace script {

static float g_values[6] = { 4091.71f, 0.0f, -2.5f, 23.4609375f, 1.5e-7f, 0.0f };
static float g_setpoint = 0.0f;
static uint8_t g_timeouts = 0;

static float get_a1() { return g_values[0]; }
static float get_a2() { return g_values[1]; }
static float get_a3() { return g_values[2]; }
static float get_b1() { return g_values[3]; }
static float get_b2() { return g_values[4]; }
static float get_sp() { return g_setpoint; }
static void  set_sp(float v) { g_setpoint = v; }
static float get_idx(uint8_t i) { return g_values[i] * 2.0f; }
static void  set_idx(uint8_t i, float v) { g_values[i] = v; }
static void  on_timeout() { ++g_timeouts; g_setpoint = -1.0f; }

using mist1::com1::Channel;
using mist1::com1::IndexedChannel;

MakeChannelMap(lookup, 8, ({
    Channel{ 'a', 1, &get_a1, nullptr },
    Channel{ 'a', 2, &get_a2, nullptr },
    Channel{ 'a', 3, &get_a3, nullptr },
    Channel{ 'b', 1, &get_b1, nullptr },
    Channel{ 'b', 2, &get_b2, nullptr },
    Channel{ 's', 1, &get_sp, &set_sp },
    Channel{ 'w', 1, nullptr, &set_sp },
    IndexedChannel('x', 1, &get_idx, &set_idx, 5),
  })
);

struct Step {
  uint32_t time_ms;     // time passed to service()
  const char* line;     // received line, or nullptr for "nothing received"
};

static const Step steps[] = {
  {    0, "I" },
  {    1, "A" },
  {    2, "ga1" }, {  3, "ga2" }, {  4, "ga3" }, {  5, "gb1" }, {  6, "gb2" }, {  7, "gx1" },
  // (no exact .5 ties at the requested precision: C libraries round those differently)
  {    8, "q01a13" }, {  9, "q01a16" }, { 10, "q01a31" }, { 10, "q01b10" }, { 11, "q01b23" }, { 12, "q01b16" },
  {   13, "ss112.5" }, { 14, "gs1" },
  {   15, "Ss1-3" }, { 16, "gs1" },
  {   17, "Ss11e3" }, { 18, "gs1" },
  {   19, "Sw10.25" }, { 20, "gs1" },
  {   21, "Sx17" }, { 22, "gx1" }, { 23, "A" },
  // errors
  {   24, "Sa15" }, { 25, "gw1" }, { 26, "gz9" }, { 27, "Ss1" }, { 28, "Ss1abc" }, { 29, "Ss11.5x" },
  {   30, "Ss1nan" }, { 31, "Ss1inf" }, { 32, "q05a13" }, { 33, "q01a17" }, { 34, "q01a1" },
  {   35, "?" }, { 36, "Pabc" },
  // streaming every 100 ms, then off
  {   40, "P100" },
  {  100, nullptr }, { 139, nullptr }, { 140, nullptr }, { 141, nullptr }, { 240, nullptr },
  {  900, nullptr }, { 950, nullptr }, { 1000, nullptr },
  { 1001, "P0" }, { 1500, nullptr },
  // values the legacy single query cannot represent
  { 1501, "Ss11.5e-12" }, { 1502, "q01s13" }, { 1503, "gs1" },
  { 1504, "Ss12.5e10" },  { 1505, "q01s13" }, { 1506, "gs1" },
  { 1507, "Ss15" },
  // communication timeout of 500 ms: fires once, clears on the next valid command
  { 1600, nullptr }, { 2006, nullptr }, { 2007, nullptr }, { 3000, nullptr },
  { 3001, "gs1" }, { 3400, nullptr }, { 3600, nullptr },
};

static const Step* g_step = nullptr;
static char g_line[32];

static char* read_step()
{
  g_line[0] = '\0';
  if (g_step != nullptr && g_step->line != nullptr) {
    uint8_t i = 0;
    for (; g_step->line[i] != '\0' && static_cast<size_t>(i) + 1 < sizeof(g_line); ++i)
    { g_line[i] = g_step->line[i]; }
    g_line[i] = '\0';
  }
  return g_line;
}

static void write_reply(char* str) { emit(str); }

static void emit_number(const char* label, uint32_t value)
{
  char text[32];
  uint8_t pos = 0;
  for (; label[pos] != '\0'; ++pos)
  { text[pos] = label[pos]; }
  char digits[11];
  uint8_t n = 0;
  do { digits[n++] = static_cast<char>('0' + value % 10); value /= 10; } while (value != 0);
  while (n != 0)
  { text[pos++] = digits[--n]; }
  text[pos] = '\0';
  emit(text);
}

static void run()
{
  static mist1::com1::IOHandler<160> io(read_step, write_reply);
  static mist1::com1::SerialDevice<160, 8> device(io, lookup);

  device.set_identity("ScriptDevice", "1.2.3");
  device.set_comm_timeout(500, &on_timeout);

  for (const Step& step : steps) {
    g_step = &step;
    char header[48];
    uint8_t pos = 0;
    header[pos++] = '>';
    header[pos++] = ' ';
    const char* shown = step.line != nullptr ? step.line : "(tick)";
    for (uint8_t i = 0; shown[i] != '\0' && static_cast<size_t>(pos) + 1 < sizeof(header); ++i)
    { header[pos++] = shown[i]; }
    header[pos] = '\0';
    emit(header);
    device.service(step.time_ms);
    if (device.comm_lost())
      emit("  [comm lost]");
  }

  emit_number("timeouts=", g_timeouts);
  emit("DONE");
}

} // namespace script

#endif // libcom1_tests_script_h
