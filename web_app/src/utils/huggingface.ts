/**
 * HuggingFace Datasets Server API Client
 * 
 * Query datasets hosted on HuggingFace Hub using the free Datasets Server API.
 * No authentication required for public datasets!
 * 
 * API Docs: https://huggingface.co/docs/datasets-server
 */

const DATASETS_SERVER_URL = 'https://datasets-server.huggingface.co';

export interface HFDatasetConfig {
  dataset: string;      // e.g., "CommunityOne/oral-health-nonprofits"
  config?: string;      // Default: "default"
  split: string;        // e.g., "organizations", "financials"
}

export interface HFRow {
  row_idx: number;
  row: Record<string, any>;
  truncated_cells: string[];
}

export interface HFRowsResponse {
  features: Array<{
    feature_idx: number;
    name: string;
    type: any;
  }>;
  rows: HFRow[];
  num_rows_total: number;
  num_rows_per_page: number;
  partial: boolean;
}

export interface HFSearchResponse {
  features: Array<{
    feature_idx: number;
    name: string;
    type: any;
  }>;
  rows: HFRow[];
  num_rows_total: number;
  num_rows_per_page: number;
  partial: boolean;
  truncated: boolean;
}

/**
 * Fetch rows from a HuggingFace dataset
 * 
 * @param config - Dataset configuration
 * @param offset - Starting row (default: 0)
 * @param length - Number of rows to fetch (max: 100)
 * @returns Promise with dataset rows
 * 
 * @example
 * const nonprofits = await fetchHFRows({
 *   dataset: "CommunityOne/oral-health-nonprofits",
 *   split: "organizations"
 * }, 0, 100);
 */
export async function fetchHFRows(
  config: HFDatasetConfig,
  offset = 0,
  length = 100
): Promise<HFRowsResponse> {
  const params = new URLSearchParams({
    dataset: config.dataset,
    config: config.config || 'default',
    split: config.split,
    offset: offset.toString(),
    length: Math.min(length, 100).toString() // API max is 100
  });

  const url = `${DATASETS_SERVER_URL}/rows?${params}`;
  
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`HuggingFace API error: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Search within a HuggingFace dataset
 * 
 * @param config - Dataset configuration
 * @param query - Search query string
 * @param offset - Starting row (default: 0)
 * @param length - Number of results (max: 100)
 * @returns Promise with search results
 * 
 * @example
 * const dentalOrgs = await searchHFDataset({
 *   dataset: "CommunityOne/oral-health-nonprofits",
 *   split: "organizations"
 * }, "dental");
 */
export async function searchHFDataset(
  config: HFDatasetConfig,
  query: string,
  offset = 0,
  length = 100
): Promise<HFSearchResponse> {
  const params = new URLSearchParams({
    dataset: config.dataset,
    config: config.config || 'default',
    split: config.split,
    query: query,
    offset: offset.toString(),
    length: Math.min(length, 100).toString()
  });

  const url = `${DATASETS_SERVER_URL}/search?${params}`;
  
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`HuggingFace search error: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get dataset size (number of rows)
 * 
 * @param config - Dataset configuration
 * @returns Promise with dataset size info
 */
export async function getHFDatasetSize(config: HFDatasetConfig): Promise<{
  dataset: string;
  config: string;
  split: string;
  num_rows_total: number;
  num_rows_per_page: number;
  partial: boolean;
}> {
  const params = new URLSearchParams({
    dataset: config.dataset,
    config: config.config || 'default',
    split: config.split
  });

  const url = `${DATASETS_SERVER_URL}/size?${params}`;
  
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`HuggingFace API error: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Fetch all nonprofits (paginated helper)
 * 
 * @param dataset - HuggingFace dataset name
 * @param split - Dataset split (default: "organizations")
 * @param maxRows - Maximum total rows to fetch
 * @returns Promise with all rows combined
 * 
 * @example
 * const allNonprofits = await fetchAllNonprofits(
 *   "CommunityOne/oral-health-nonprofits",
 *   "organizations",
 *   1000
 * );
 */
export async function fetchAllNonprofits(
  dataset: string,
  split = 'organizations',
  maxRows = 1000
): Promise<any[]> {
  const allRows: any[] = [];
  let offset = 0;
  const batchSize = 100; // API max per request
  
  while (offset < maxRows) {
    const response = await fetchHFRows(
      { dataset, split },
      offset,
      Math.min(batchSize, maxRows - offset)
    );
    
    const rows = response.rows.map(r => r.row);
    allRows.push(...rows);
    
    // Stop if we've fetched all available rows
    if (rows.length < batchSize) {
      break;
    }
    
    offset += batchSize;
  }
  
  return allRows;
}

/**
 * Filter nonprofits by state
 * 
 * @param dataset - HuggingFace dataset name
 * @param stateCode - Two-letter state code (e.g., "AL", "CA")
 * @param maxRows - Maximum rows to fetch
 * @returns Promise with filtered nonprofits
 * 
 * @example
 * const alabamaNonprofits = await fetchNonprofitsByState(
 *   "CommunityOne/one-nonprofits-organizations",
 *   "AL",
 *   5000
 * );
 */
export async function fetchNonprofitsByState(
  dataset: string,
  stateCode: string,
  maxRows = 5000
): Promise<any[]> {
  const allRows = await fetchAllNonprofits(dataset, 'organizations', maxRows);
  return allRows.filter(row => row.state === stateCode);
}

/**
 * Filter nonprofits by NTEE code
 * 
 * @param dataset - HuggingFace dataset name
 * @param nteePrefix - NTEE code prefix (e.g., "E" for health, "X" for religion)
 * @param maxRows - Maximum rows to fetch
 * @returns Promise with filtered nonprofits
 * 
 * @example
 * const healthOrgs = await fetchNonprofitsByNTEE(
 *   "CommunityOne/one-nonprofits-organizations",
 *   "E",
 *   10000
 * );
 */
export async function fetchNonprofitsByNTEE(
  dataset: string,
  nteePrefix: string,
  maxRows = 10000
): Promise<any[]> {
  const allRows = await fetchAllNonprofits(dataset, 'organizations', maxRows);
  return allRows.filter(row => row.ntee_code?.startsWith(nteePrefix));
}

/**
 * Nonprofit search with filters
 * 
 * @param options - Search options
 * @returns Promise with search results
 * 
 * @example
 * const results = await searchNonprofits({
 *   dataset: "CommunityOne/one-nonprofits-organizations",
 *   query: "dental",
 *   state: "CA",
 *   nteeCode: "E",
 *   limit: 100
 * });
 */
export async function searchNonprofits(options: {
  dataset: string;
  query?: string;
  state?: string;
  nteeCode?: string;
  limit?: number;
}): Promise<any[]> {
  const { dataset, query, state, nteeCode, limit = 100 } = options;
  
  let results: any[];
  
  if (query) {
    // Use HuggingFace search API
    const response = await searchHFDataset(
      { dataset, split: 'organizations' },
      query,
      0,
      limit
    );
    results = response.rows.map(r => r.row);
  } else {
    // Fetch and filter
    results = await fetchAllNonprofits(dataset, 'organizations', limit);
  }
  
  // Apply filters
  if (state) {
    results = results.filter(row => row.state === state);
  }
  
  if (nteeCode) {
    results = results.filter(row => row.ntee_code?.startsWith(nteeCode));
  }
  
  return results.slice(0, limit);
}
