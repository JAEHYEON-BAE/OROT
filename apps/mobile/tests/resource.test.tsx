import { act, renderHook, waitFor } from "@testing-library/react-native";
import { useResource } from "../src/lib/api/use-resource";
test("a late response from the previous sort cannot overwrite the latest result", async () => {
  let oldResolve!: (value: string) => void;
  const old = new Promise<string>((resolve) => {
    oldResolve = resolve;
  });
  const { result, rerender } = renderHook<ReturnType<typeof useResource<string>>, { sort: string }>(
    ({ sort }) =>
      useResource(sort, () =>
        sort === "old" ? old : Promise.resolve("latest"),
      ),
    { initialProps: { sort: "old" } },
  );
  rerender({ sort: "new" });
  await waitFor(() => expect(result.current.data).toBe("latest"));
  await act(async () => {
    oldResolve("stale");
    await old;
  });
  expect(result.current.data).toBe("latest");
});
