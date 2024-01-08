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

let dogroups;


const config = {
    gap_x: 1,
    gap_y: 1,
    node_size: 5,
    edge_size: 1,
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

async function init() {
   // Initialize our JS objects.
   container = document.getElementById("do-group-tree");
   graph = new graphology.Graph();

   // Load all the data objects.
   // You want to do this asynchronous, since loading this data might take quite a while
   let response = await fetch("/members/dogroups/data").then(res => res.json());
   dogroups = response;
}

function createDoGroupGraph() {
    let graph = new graphology.Graph();

    /**
     * Stores the count of relations from a dogroup a to b.
     * @type {{number: {number: {number}}}}
     */
    let connections = {};
    dogroups.map((dogroup) => {
        if (!(dogroup.id in connections)) {
            connections[dogroup.id] = {};
        }
        dogroup.generations.map((generation) => {
            generation.parents.filter((parent) => parent.previous_dogroup !== null).map((parent) => {
                if (!(parent.previous_dogroup in connections[dogroup.id])) {
                    connections[dogroup.id][parent.previous_dogroup] = 0;
                }
                connections[dogroup.id][parent.previous_dogroup] += 1;
            });
        });
    });

    // TODO: Figure out automated layouts: https://graphology.github.io/standard-library/layout-force.html

    // Add a node for each dogroup.
    dogroups.map((dogroup, i) => {
        graph.addNode(dogroup.id, {
            label: dogroup.name,
            color: dogroup.color,
            x: i,
            y: i,
        });
    });

    Object.keys(connections).map((source) => {
        Object.keys(connections[source]).map((target) => {
            graph.addEdge(source, target, { size: connections[source][target] });
        });
    });

    return graph;
}

function createTreeGraph() {
    let graph = new graphology.Graph();
    let years = dogroups
        .map((dogroup) => dogroup.generations.map((generation) => generation.year))
        .reduce((prev, curr) => {
            curr.map((year) => prev.add(year));
            return prev;
        }, new Set())
    years = [...years].sort((a, b) => b - a);

    // Give every dogroup its own x coordinate
    let dogroup_x_coords = {};
    let current_x_coord = 0;
    dogroups.map((dogroup) => {
        dogroup_x_coords[dogroup.id] = current_x_coord;
        current_x_coord += config.gap_x;
    });

    // Give every Kick-In year its own y coordinate
    let year_y_coords = {};
    let current_y_coord = 0;
    years.map((year) => {
        year_y_coords[year] = current_y_coord;
       current_y_coord += config.gap_y;
    });

    // Start adding in all the nodes.
    dogroups.map((dogroup) => {
        dogroup.generations.map((generation) => {
            graph.addNode(generation.id, {
                x: dogroup_x_coords[dogroup.id],
                y: year_y_coords[generation.year],
                label: dogroup.name + " " + generation.year,
                color: generation.color,
                size: config.node_size,
            });
        });
    });

    // Start adding in all the edges.
    dogroups.map((dogroup) => {
        dogroup.generations.map((generation) => {
            createdLinks = new Set();
            generation.parents.filter((parent) => parent.previous_dogroup_generation !== null).map((parent) => {
                if (!createdLinks.has(parent.previous_dogroup_generation)) {
                    graph.addEdge(generation.id, parent.previous_dogroup_generation, {size: config.edge_size});
                    createdLinks.add(parent.previous_dogroup_generation);
                }
            });
        });
    });

    return graph;
}

function render(graph) {
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
   });

   renderer.setSetting("nodeReducer", (node, data) => {
      const res = {...data};

      if (state.hoveredNeighbours && !state.hoveredNeighbours.includes(node) && state.hoveredNode !== node) {
         // Set opacity (but hey that is of course supported :), so hotfix instead!)
         res.color = res.color.slice(0, 7) + "60";
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
}

window.addEventListener('DOMContentLoaded', async function() {
    await init();

    // let graph = createTreeGraph();
    let graph = createDoGroupGraph();
    render(graph);
});
