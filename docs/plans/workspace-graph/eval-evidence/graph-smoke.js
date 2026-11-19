// Run in the browser console on /workspace-map/?view=graph with no filters.
(async () => {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const index = await (await fetch("workspace-index.json")).json();
  const byPath = new Map(index.files.map(file => [file.relativePath, file]));
  const nodes = [...document.querySelectorAll(".graph-file")];
  const paths = nodes.map(node => node.dataset.graphFile);
  assert(paths.length === byPath.size && new Set(paths).size === byPath.size, "Missing or duplicate file node");
  for (const edge of document.querySelectorAll(".graph-edge")) {
    const file = byPath.get(edge.dataset.file);
    assert(file, "Edge references a missing file");
    const groups = new URLSearchParams(location.search).get("group") === "folder"
      ? [file.folder.split("/")[0] || "."]
      : (file.topics.length ? file.topics : ["__untagged"]);
    assert(groups.includes(edge.dataset.group), "Invented membership edge");
  }
  const fixture = [
    { relativePath: "one.md", folder: "folder/nested", topics: ["x", "x", "y"] },
    { relativePath: "root.md", folder: "", topics: [] },
  ];
  const topics = graphLayout(fixture, "topic");
  const folders = graphLayout(fixture, "folder");
  assert(topics.files.length === 2, "Layout lost a file");
  assert(topics.files[0].groups.length === 2, "Duplicate tag created duplicate membership");
  assert(topics.groups.some(group => group.key === "__untagged" && group.count === 1), "Untagged file lost");
  assert(folders.groups.some(group => group.key === "." && group.count === 1), "Root file lost");
  assert(folders.groups.some(group => group.key === "folder" && group.count === 1), "Nested folder membership lost");
  assert(graphLayout([], "topic").files.length === 0, "Empty layout contains files");
  const result = { status: "pass", files: paths.length, edges: document.querySelectorAll(".graph-edge").length };
  console.log(result);
  return result;
})();
