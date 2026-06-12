// Minimal ambient declarations for the `leaflet.markercluster` plugin.
// The upstream @types/leaflet.markercluster package can't be installed in this
// environment (read-only node_modules/@types), so we declare just the slice of
// the API we use. The plugin augments the global `L` namespace at runtime.
import 'leaflet'

declare module 'leaflet' {
  interface MarkerClusterGroupOptions extends L.LayerOptions {
    showCoverageOnHover?: boolean
    zoomToBoundsOnClick?: boolean
    spiderfyOnMaxZoom?: boolean
    removeOutsideVisibleBounds?: boolean
    chunkedLoading?: boolean
    maxClusterRadius?: number | ((zoom: number) => number)
    iconCreateFunction?: (cluster: MarkerCluster) => L.Icon | L.DivIcon
  }

  interface MarkerCluster extends L.Marker {
    getChildCount(): number
    getAllChildMarkers(): L.Marker[]
  }

  interface MarkerClusterGroup extends L.FeatureGroup {
    addLayer(layer: L.Layer): this
    addLayers(layers: L.Layer[]): this
    removeLayers(layers: L.Layer[]): this
    clearLayers(): this
  }

  function markerClusterGroup(
    options?: MarkerClusterGroupOptions,
  ): MarkerClusterGroup
}
