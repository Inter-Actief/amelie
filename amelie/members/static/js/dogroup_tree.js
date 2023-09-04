/** The HTML container that contains our visualization */
var container;

/** The graph containing the actual graph datastructure */
var graph;

/** The renderer taking care of the rendering of this structure */
var renderer;

/** Keeps track of the state of hovered over nodes */
var state = {
   hoveredNode: null,
   hoveredNeighbours: null
};

/**
 * Store nodes on a hover event.
 * @param node The node that is being hovered over.
 */
function setHoveredNode(node) {
   if (node !== null) {
      state.hoveredNode = node;
      state.hoveredNeighbours = graph.neighbors(node);
   } else {
      state.hoveredNode = null;
      state.hoveredNeighbours = null;
   }
   renderer.refresh();
}

window.addEventListener('DOMContentLoaded', async function() {
   // Initialize our JS objects.
   container = document.getElementById("do-group-tree");
   graph = new graphology.Graph();

   // Constants that determine the sizes and distances between nodes.
   let gap_x = 1;
   let gap_y = 1;
   let node_size = 5;
   let edge_size = 1;

   // Load all the data objects.
   // You want to do this asynchronous, since loading this data might take quite a while
   let response = await fetch("/members/dogroups/data").then(res => res.json());
   let dogroups = response.dogroups;
   let years = response.years;
   let data = response.data;

   // Give every dogroup its own x coordinate
   let dogroup_x_coords = {};
   let current_x_coord = 0;
   for (let i in dogroups) {
      dogroup_x_coords[dogroups[i]] = current_x_coord;
      current_x_coord += gap_x;
   }

   // Give every Kick-In year its own y coordinate
   let year_y_coords = {};
   let current_y_coord = 0;
   for (let i in years.reverse()) {
      year_y_coords[years[i]] = current_y_coord;
      current_y_coord += gap_y;
   }

   // Start adding in all the nodes.
   for(let i in dogroups) {
      let dogroup = dogroups[i];
      for (let year in data[dogroup]) {
         let generation = data[dogroup][year];
         graph.addNode(generation.id, {x: dogroup_x_coords[dogroup],
                                          y: year_y_coords[year],
                                          label: dogroup + " " + year,
                                          color: generation.color,
                                          size: node_size});
      }
   }

   // Start adding in all the edges.
   for (let i in dogroups) {
      let dogroup = dogroups[i];
      for (let year in data[dogroup]) {
         let generation = data[dogroup][year];
         let generation_id = generation['id'];
         for (let _id in generation['parents']) {
            let parent_id = generation['parents'][_id]['id'];
            graph.addEdge(generation_id, parent_id, {size: edge_size})
         }
      }
   }

   // Empty the container of all of its child nodes.
   while (container.hasChildNodes()) {
      container.removeChild(container.firstChild);
   }

   renderer = new Sigma(graph, container);

   renderer.on("enterNode", ({ node }) => {
      setHoveredNode(node);
   });
   renderer.on("leaveNode", () => {
      setHoveredNode(null);
   })

   renderer.setSetting("nodeReducer", (node, data) => {
      const res = {...data};

      if (state.hoveredNeighbours && !state.hoveredNeighbours.includes(node) && state.hoveredNode !== node) {
         res.label = "";
         res.color = "#f6f6f6";
      }

      return res;
   });
   renderer.setSetting("edgeReducer", (edge, data) => {
      const res = {...data};

      if (state.hoveredNode && !graph.hasExtremity(edge, state.hoveredNode)) {
         res.hidden = true;
      }

      return res;
   });

   const layout = new ForceSupervisor(graph);
   layout.start();
});
