import { fireEvent, render } from "@testing-library/react-native";
import * as Native from "react-native";
import { ThemeText } from "../src/components/theme-text";
import { RecordArt } from "../src/components/record-art";
import { theme } from "../theme";

// Exercise an optional theme image without downloading any real asset.
jest.mock("../theme", () => {
  const actual = jest.requireActual("../theme");
  return {
    ...actual,
    theme: {
      ...actual.theme,
      images: {
        ...actual.theme.images,
        recordPlaceholder: () => ({
          uri: "https://example.invalid/fallback.png",
        }),
      },
    },
  };
});

afterEach(() => jest.restoreAllMocks());

test("text uses the selected typography and follows light/dark changes", () => {
  const scheme = jest.spyOn(Native, "useColorScheme").mockReturnValue("light");
  const screen = render(
    <ThemeText testID="title" variant="hero" allowFontScaling>
      OROT
    </ThemeText>,
  );
  expect(screen.getByTestId("title")).toHaveStyle({
    color: theme.colors.light.text,
    fontSize: theme.typography.hero.fontSize,
    lineHeight: theme.typography.hero.lineHeight,
  });
  scheme.mockReturnValue("dark");
  screen.rerender(
    <ThemeText testID="title" variant="hero" allowFontScaling>
      OROT
    </ThemeText>,
  );
  expect(screen.getByTestId("title")).toHaveStyle({
    color: theme.colors.dark.text,
  });
  expect(screen.getByTestId("title").props.allowFontScaling).toBe(true);
});

test("failed cover falls back to theme image, then graphic, and a new URL can load", () => {
  const screen = render(<RecordArt uri="https://example.invalid/cover.png" />);
  fireEvent(screen.UNSAFE_getByType(Native.Image), "error");
  expect(screen.UNSAFE_getByType(Native.Image).props.source).toEqual({
    uri: "https://example.invalid/fallback.png",
  });
  fireEvent(screen.UNSAFE_getByType(Native.Image), "error");
  expect(screen.UNSAFE_queryByType(Native.Image)).toBeNull();
  screen.rerender(<RecordArt uri="https://example.invalid/new.png" />);
  expect(screen.UNSAFE_getByType(Native.Image).props.source).toEqual({
    uri: "https://example.invalid/new.png",
  });
});

test("missing or unsafe cover uses the configured placeholder", () => {
  const screen = render(<RecordArt uri="javascript:alert(1)" />);
  expect(screen.UNSAFE_getByType(Native.Image).props.source).toEqual({
    uri: "https://example.invalid/fallback.png",
  });
});
