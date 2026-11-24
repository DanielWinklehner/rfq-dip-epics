// R4 c: runs conversation.txt through the PC build of InterlockOpta and prints the transcript
// that emulation/sim/tools/interlock_replay.py prints for the simulator.
//
//   replay_device conversation.txt > replay_c.txt
//
// Exit code 1 when the firmware reports the doors differently from the file's "doors" column
// (then the file does not describe the firmware, and the comparison would mean nothing).

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "box.hpp"

int main(int argc, char** argv)
{
  if (argc != 2) {
    fprintf(stderr, "usage: %s conversation.txt\n", argv[0]);
    return 2;
  }
  FILE* f = fopen(argv[1], "r");
  if (f == nullptr) {
    perror(argv[1]);
    return 2;
  }
  box::power_on();
  char text[256];
  int number = 0;
  int bad = 0;
  while (fgets(text, sizeof(text), f) != nullptr) {
    ++number;
    text[strcspn(text, "\r\n")] = '\0';
    if (text[0] == '#' || text[0] == '\0')
      continue;
    unsigned long ms;
    int l1, l2;
    char doors[3];
    int consumed = 0;
    if (sscanf(text, "%lu %d %d %2s %n", &ms, &l1, &l2, doors, &consumed) != 4 || consumed == 0) {
      fprintf(stderr, "%s:%d: cannot parse \"%s\"\n", argv[1], number, text);
      return 2;
    }
    const char* line = text + consumed;
    const bool none = strcmp(line, "-") == 0;
    box::step((uint32_t)ms, l1 != 0, l2 != 0, none ? nullptr : line);
    char reported[3] = { interlock_opta::get_door(0) == 1.0f ? '1' : '0',
                         interlock_opta::get_door(1) == 1.0f ? '1' : '0', '\0' };
    if (strcmp(reported, doors) != 0) {
      fprintf(stderr, "%s:%d: at %lu ms the firmware reports doors %s, the file says %s\n",
              argv[1], number, ms, reported, doors);
      bad = 1;
    }
    printf("> %lu doors=%s %s\n", ms, doors, none ? "(nothing)" : line);
    for (int i = 0; i < box::g_reply_count && i < 8; ++i)
      printf("%s\n", box::g_replies[i]);
  }
  fclose(f);
  return bad;
}
