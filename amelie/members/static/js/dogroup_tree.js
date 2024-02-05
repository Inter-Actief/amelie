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

let gravityConstant = 0.9;
let forceConstant = 100;
let differenceConstant = 500;

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

function determineForces(nodes, connections) {
    // apply force between nodes
    nodes.forEach(node => {
        node.force_x = node.x * -1 * gravityConstant;
        node.force_y = node.y * -1 * gravityConstant;
    });

    // apply recursive force between nodes
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
            const node1 = nodes[i];
            const node2 = nodes[j];

            const pos_x = node1.x;
            const pos_y = node1.y;
            const dir_x = node2.x - pos_x;
            const dir_y = node2.y - pos_y;
            let force_x = dir_x / (Math.sqrt(dir_x ** 2 + dir_y ** 2) ** 2);
            let force_y = dir_y / (Math.sqrt(dir_x ** 2 + dir_y ** 2) ** 2);
            force_x *= forceConstant;
            force_y *= forceConstant;

            nodes[i].force_x += force_x * -1;
            nodes[i].force_y += force_y * -1;
            nodes[j].force_x += force_x;
            nodes[j].force_y += force_y;
        }
    }

    // apply forces to the edges.
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
            let a = null;
            let b = null;

            if (!!connections[nodes[i].key] && !!connections[nodes[i].key][nodes[j].key]) {
                a = nodes[i];
                b = nodes[j];
            } else if (!!connections[nodes[j].key] && !!connections[nodes[j].key][nodes[i].key]) {
                a = nodes[j];
                b = nodes[i];
            } else {
                // If dogroups are not associated with each other, then push them apart.
                nodes[i].force_x -= differenceConstant * .1;
                nodes[i].force_y -= differenceConstant * .1;
                nodes[j].force_x += differenceConstant * .1;
                nodes[j].force_y += differenceConstant * .1;
                continue;
            }

            // const diff_x = a.x - b.x;
            // const diff_y = a.y - b.y;
            const difference = connections[a.key][b.key] * differenceConstant;
            nodes[i].force_x += difference;
            nodes[i].force_y += difference;
            nodes[j].force_x -= difference;
            nodes[j].force_y -= difference;
        }
    }
}

function createDoGroupGraph() {
    let graph = new graphology.Graph();

    /**
     * Stores the count of relations from a dogroup a to b.
     * @type {{number: {number: {number}}}}
     */
    let connections = {};

    // Create a connection from a dogroup to another dogroup if their parent was from that dogroup.
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

    // Count how many connections are in total associated to this dogroup.
    let connectionCount = {};
    Object.keys(connections).map((dogroup) => {
        connectionCount[dogroup] = Object.values(connections[dogroup]).reduce((accumulator, count) => accumulator + count, 0);
    });

    // TODO: Figure out automated layouts: https://graphology.github.io/standard-library/layout-force.html

    // Add a node for each dogroup.
    let nodes = [];
    dogroups
        .map((dogroup, i) => {
            nodes.push({
                key: dogroup.id,
                label: dogroup.name,
                color: dogroup.color,
                size: 1, //dogroup.generations.length,
                x: Math.floor(i/10),
                y: i%10,
            });
        });

    for (let i = 0; i < 10; i++) {
        determineForces(nodes, connections);
    }


    // Apply the calculated forces to the node their positions.
    for (let i = 0; i < nodes.length; i++) {
        if (!!connectionCount[nodes[i].key]) {
            nodes[i].x += nodes[i].force_x / connectionCount[nodes[i].key];// * nodes[i].size;
            nodes[i].y += nodes[i].force_y / connectionCount[nodes[i].key];// * nodes[i].size;
        } else {
            nodes[i].x += nodes[i].force_x;// * nodes[i].size;
            nodes[i].y += nodes[i].force_y;// * nodes[i].size;
        }


    }

    nodes.forEach(node => {
        graph.addNode(node.key, node);
    })

    Object.keys(connections).map((source) => {
        Object.keys(connections[source]).map((target) => {
            graph.addEdge(source, target, {
                size: connections[source][target],
            });

            // console.log(connections[source][target]);
        });
    });
    return graph;
}

function createTreeGraph() {
    let graph = new graphology.Graph();

    // Get all the available years.
    let years = dogroups
        .map((dogroup) => dogroup.generations.map((generation) => generation.year))
        .reduce((prev, curr) => {
            curr.map((year) => prev.add(year));
            return prev;
        }, new Set());
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
