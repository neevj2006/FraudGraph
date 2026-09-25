"use client";
import { useEffect, useRef, useState } from "react";
import type { Core } from "cytoscape";
import { Expand, Minus, Plus } from "lucide-react";
import type { Graph } from "../lib/api";
const colors: Record<string, string> = {transaction: "#587d8d", account: "#8874b5", card: "#c7984b", device: "#388b76", address: "#bf8175", merchant: "#739165"};
export default function EvidenceGraph({ graph, onEntity }: {graph: Graph; onEntity: (id: string) => void}) {
  const ref = useRef<HTMLDivElement>(null), cy = useRef<Core | null>(null);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    let dead = false;
    import("cytoscape").then(({ default: cytoscape }) => {
      if (dead || !ref.current) return;
      const focal = graph.nodes.find(n => n.focal)?.id;
      const signatures = new Set(graph.edges.filter(e => e.source === focal).map(e => e.target));
      const focusedEdges = graph.edges.filter(e => signatures.has(e.target));
      const visible = new Set(focusedEdges.flatMap(e => [e.source, e.target]));
      if (focal) visible.add(focal);
      const instance = cytoscape({container: ref.current, elements: [
        ...graph.nodes.filter(n => visible.has(n.id)).map(n => ({data: {...n, color: n.focal ? "#184f40" : colors[n.type], size: n.focal ? 40 : n.type === "transaction" ? 16 : 28}})),
        ...focusedEdges.map(e => ({data: e}))],
        style: [{selector: "node", style: {"background-color": "data(color)", width: "data(size)", height: "data(size)", label: "data(label)", "font-size": 9, "text-valign": "bottom", "text-margin-y": 7, color: "#55645e", "border-width": 3, "border-color": "#fff"}},
          {selector: "edge", style: {width: 1, "line-color": "#cbd8d0", "curve-style": "bezier", opacity: .6}},
          {selector: 'node[type = "transaction"]', style: {label: ""}},
          {selector: "node[?focal]", style: {label: "data(label)", "font-weight": "bold"}},
          {selector: ":selected", style: {"border-color": "#b98c31", "border-width": 4, label: "data(label)"}},
          {selector: ".dim", style: {opacity: .15}}],
        layout: {name: "concentric", animate: false, concentric: n => n.data("focal") ? 3 : n.data("type") === "transaction" ? 1 : 2, levelWidth: () => 1, minNodeSpacing: 12, padding: 25},
        minZoom: .2, maxZoom: 3, wheelSensitivity: .2});
      instance.on("tap", "node", event => { const n = event.target; setSelected(n.data("label")); instance.elements().removeClass("dim"); instance.elements().difference(n.closedNeighborhood()).addClass("dim"); });
      instance.on("tap", event => {if (event.target === instance) {instance.elements().removeClass("dim"); setSelected("");}});
      cy.current = instance;
    });
    return () => { dead = true; cy.current?.destroy(); cy.current = null; };
  }, [graph]);
  return <div className="graph-wrap"><div className="graph-canvas" ref={ref} aria-label="Interactive transaction evidence graph" role="img" />
    <div className="graph-tools"><button aria-label="Zoom in" onClick={() => cy.current?.zoom(cy.current.zoom() * 1.2)}><Plus size={16}/></button><button aria-label="Zoom out" onClick={() => cy.current?.zoom(cy.current.zoom() / 1.2)}><Minus size={16}/></button><button aria-label="Fit graph" onClick={() => cy.current?.fit(undefined, 25)}><Expand size={16}/></button></div>
    <span className="graph-hint">{selected || "Select a node to trace its connections"}</span>
    <div className="legend">{Object.entries(colors).map(([name, color]) => <span key={name}><i style={{background: color}}/>{name}</span>)}</div>
    <details className="graph-list"><summary>Accessible entity list · {graph.nodes.length} nodes</summary><div>{graph.nodes.filter(n => n.type !== "transaction").map(n => <button key={n.id} onClick={() => onEntity(n.id)}>{n.label}</button>)}</div></details>
  </div>;
}
