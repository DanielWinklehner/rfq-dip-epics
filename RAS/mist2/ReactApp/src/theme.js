import { amber, blue, grey, purple, red } from "@mui/material/colors";
import rasThemes from "React-Automation-Studio/components/UI/Themes/themes";

// The RAS themes, each with the alarm colours of the MIST-2 GUI (LAYOUT.md 1.2):
// amber MINOR, red MAJOR, purple INVALID, grey for a lost connection. The
// emulator banner uses blue, a colour no alarm uses (LAYOUT.md 1.3).
const alarm = {
  minor: { light: amber[200], main: amber[600], dark: amber[800] },
  major: { light: red[300], main: red[600], dark: red[800] },
  invalid: { light: purple[200], main: purple[400], dark: purple[700] },
  disconnected: { light: grey[400], main: grey[600], dark: grey[800] },
};
const emulator = { light: blue[600], main: blue[800], dark: blue[900] };

const themes = Object.fromEntries(
  Object.entries(rasThemes).map(([name, theme]) => [
    name,
    {
      ...theme,
      palette: {
        ...theme.palette,
        alarm: { ...theme.palette.alarm, ...alarm },
        emulator,
      },
    },
  ])
);

export const defaultTheme = "Dark";
export default themes;
