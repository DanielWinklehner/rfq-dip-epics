import drawings from "../config/drawings.json";
import { alarmPvs, installedDevices } from "../registry";
import { tagHeight } from "./Tag";

export const overview = "Overview";
const defaultTagWidth = 210;

export const drawingOf = (page) => drawings.pages[page];

// The devices a page is about: all of them on the overview, else its own.
const devicesOf = (page) => (page === overview ? installedDevices() : installedDevices(page));

// Tags for the devices of a page that its drawing does not place, in the
// drawing's list area, column after column. A device added to the registry
// later appears here without any change to the drawing.
const listed = (page) => {
  const drawing = drawingOf(page);
  const placed = new Set(drawing.elements.map((element) => element.device));
  const { x, y, w = defaultTagWidth, h, gap = 12 } = drawing.list;
  let column = 0;
  let top = y;
  return devicesOf(page)
    .filter((id) => !placed.has(id))
    .map((id) => {
      const height = tagHeight(id);
      if (top > y && top + height > y + h) {
        column += 1;
        top = y;
      }
      const tag = { device: id, tag: { x: x + column * (w + gap), y: top, w } };
      top += height + gap;
      return tag;
    });
};

// Every element of a page: placed by the drawing, or listed.
export const elementsOf = (page) => [
  ...drawingOf(page).elements.map((element) => ({
    ...element,
    tag: element.tag && { w: defaultTagWidth, ...element.tag },
  })),
  ...listed(page),
];

// The records whose worst state is the page's: those of everything it shows.
export const pageAlarmPvs = (page) => [
  ...new Set(elementsOf(page).flatMap((element) => alarmPvs(element.device, element.channel))),
];
