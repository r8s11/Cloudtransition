/**
 * Improved Card Data Parser for Dashboard Metrics
 * 
 * Provides centralized, reusable parsing logic for card-based metrics displays.
 * Separates data extraction from presentation logic and improves maintainability.
 */

class CardDataParser {
  /**
   * Parse and normalize host data for card rendering
   * @param {Object} hostData - Raw host data from API
   * @param {string} hostName - Name of the host
   * @returns {Object} Normalized host card data
   */
  static parseHostCard(hostData, hostName) {
    const state = ["up", "down", "pending"].includes(hostData?.status) ? hostData.status : "unknown";
    const isUp = state === "up";
    
    return {
      name: hostName,
      status: state,
      metrics: {
        cpu: isUp ? (hostData?.cpu_percent ?? null) : null,
        memory: isUp ? (hostData?.memory_percent ?? null) : null,
        disk: isUp ? (hostData?.disk_percent ?? null) : null,
        cpuThreads: isUp ? (hostData?.cpu_threads ?? null) : null,
        memoryCapacity: isUp ? (hostData?.memory_total_bytes ?? null) : null,
        memoryAvailable: isUp ? (hostData?.memory_available_bytes ?? null) : null,
        diskCapacity: isUp ? (hostData?.disk_total_bytes ?? null) : null,
        diskAvailable: isUp ? (hostData?.disk_available_bytes ?? null) : null,
      },
      metadata: {
        osName: isUp ? (hostData?.os_name ?? "OS not exported") : "Unavailable",
        exporterJob: isUp ? (hostData?.exporter_job ?? "Host exporter") : null,
        uptime: isUp ? (hostData?.uptime_seconds ?? null) : null,
        platform: isUp ? (hostData?.platform ?? "unknown") : "unknown",
        systemVolume: isUp ? (hostData?.system_volume ?? null) : null,
      },
      statusText: CardDataParser.getStatusText(state, isUp),
      isLive: isUp,
      hasTelemetry: !!hostData,
    };
  }

  /**
   * Get localized status text for display
   * @param {string} state - Host status
   * @param {boolean} isUp - Whether host is up
   * @returns {string} Status text for display
   */
  static getStatusText(state, isUp) {
    if (!isUp) return { up: "Telemetry live", down: "Exporter down", pending: "Awaiting telemetry", unknown: "Unavailable" }[state] || "Unavailable";
    return { up: "Telemetry live", down: "Exporter down", pending: "Awaiting telemetry", unknown: "Unavailable" }[state] || "Telemetry live";
  }

  /**
   * Parse project data for card rendering
   * @param {Object} projectData - Raw project data from API
   * @returns {Object} Normalized project card data
   */
  static parseProjectCard(projectData) {
    return {
      name: projectData?.name,
      status: projectData?.status || "unknown",
      statusText: CardDataParser.getProjectStatusText(projectData?.status),
      lastUpdated: projectData?.last_updated,
      hasData: !!projectData,
    };
  }

  /**
   * Get project status text for display
   * @param {string} status - Project status
   * @returns {string} Status text for display
   */
  static getProjectStatusText(status) {
    return { up: "Responding", unknown: "Unavailable", unmonitored: "Not monitored" }[status] || "Unavailable";
  }

  /**
   * Parse volume data for storage card rendering
   * @param {Array} volumes - Volume data from API
   * @param {Object} hostData - Parent host data
   * @returns {Array} Normalized volume card data
   */
  static parseVolumeCards(volumes, hostData) {
    return volumes?.map((volume) => ({
      name: volume.name,
      isSystem: volume.name === hostData?.system_volume,
      usedPercent: volume.used_percent,
      availableBytes: volume.available_bytes,
      totalBytes: volume.total_bytes,
      isReadOnly: volume.readonly === true,
      hasData: !!volume,
    })) || [];
  }

  /**
   * Parse disk data for disk card rendering
   * @param {Array} disks - Disk data from API
   * @param {Object} hostData - Parent host data
   * @returns {Array} Normalized disk card data
   */
  static parseDiskCards(disks, hostData) {
    return disks?.map((disk) => ({
      device: disk.device,
      readBytesPerSecond: disk.read_bytes_per_second,
      writeBytesPerSecond: disk.write_bytes_per_second,
      busyPercent: disk.busy_percent,
      ioInProgress: disk.io_in_progress,
      hasData: !!disk,
    })) || [];
  }

  /**
   * Parse activity log data for activity card rendering
   * @param {Object} activityData - Activity data from API
   * @returns {Object} Normalized activity card data
   */
  static parseActivityCards(activityData) {
    return {
      logCount: activityData?.total_count || 0,
      errorCount: activityData?.error_count || 0,
      severityKnownCount: activityData?.severity_known_count || 0,
      sources: activityData?.sources?.slice(0, 12) || [],
      hasActivity: !!activityData,
      status: activityData?.status || "unavailable",
      logs: activityData?.rows || [],
    };
  }

  /**
   * Parse chart data for card rendering
   * @param {Object} chartData - Chart data from API
   * @param {string} hostName - Host name for context
   * @returns {Object} Normalized chart card data
   */
  static parseChartCards(chartData, hostName) {
    return {
      name: hostName,
      hasHistory: chartData?.status === "ok" && chartData?.end > chartData?.start,
      fields: ["cpu_percent", "memory_percent", "disk_percent"],
      series: chartData?.hosts?.[hostName] || {},
      window: chartData?.window,
      start: chartData?.start,
      end: chartData?.end,
      stepSeconds: chartData?.step_seconds,
      hasData: !!chartData?.hosts?.[hostName],
      status: chartData?.status || "unavailable",
    };
  }

  /**
   * Parse and validate API response data
   * @param {Object} response - Raw API response
   * @param {string} responseType - Type of response (snapshot, history, charts)
   * @returns {Object} Validated and normalized data
   */
  static parseApiResponse(response, responseType) {
    const validators = {
      snapshot: CardDataParser.validateSnapshotResponse,
      history: CardDataParser.validateHistoryResponse,
      charts: CardDataParser.validateChartsResponse,
    };

    if (validators[responseType]) {
      return validators[responseType].call(CardDataParser, response);
    }

    throw new Error(`Unknown response type: ${responseType}`);
  }

  /**
   * Validate snapshot response data
   * @param {Object} response - Raw snapshot response
   * @returns {Object} Validated snapshot data
   */
  static validateSnapshotResponse(response) {
    if (!response?.infrastructure?.hosts || !Array.isArray(response?.projects) || !Number.isFinite(new Date(response?.timestamp)?.getTime())) {
      throw new Error("Invalid snapshot response");
    }

    return {
      hosts: response.infrastructure.hosts || {},
      projects: response.projects || [],
      timestamp: response.timestamp,
      hasValidData: true,
    };
  }

  /**
   * Validate history response data
   * @param {Object} response - Raw history response
   * @returns {Object} Validated history data
   */
  static validateHistoryResponse(response) {
    if (!response?.hosts || response?.window !== this.currentWindow) {
      throw new Error("Invalid history response");
    }

    return {
      hosts: response.hosts || {},
      window: response.window,
      start: response.start,
      end: response.end,
      step_seconds: response.step_seconds,
      status: response.status || "unavailable",
      hasValidData: true,
    };
  }

  /**
   * Validate charts response data
   * @param {Object} response - Raw charts response
   * @returns {Object} Validated charts data
   */
  static validateChartsResponse(response) {
    if (!response?.rates || !response?.probes || !response?.logs || response?.window !== this.currentWindow) {
      throw new Error("Invalid charts response");
    }

    return {
      rates: response.rates || { status: "unavailable" },
      probes: response.probes || { status: "unavailable" },
      logs: response.logs || { status: "unavailable" },
      window: response.window,
      status: "ok",
      hasValidData: true,
    };
  }

  /**
   * Batch process multiple card types for efficient rendering
   * @param {Object} snapshotData - Snapshot data
   * @param {Object} historyData - History data
   * @param {Object} chartsData - Charts data
   * @returns {Object} Processed card data for rendering
   */
  static processAllCards(snapshotData, historyData, chartsData) {
    const hostNames = Object.keys(snapshotData?.hosts || {});

    return {
      hosts: hostNames.map((hostName) => CardDataParser.parseHostCard(snapshotData.hosts[hostName], hostName)),
      projects: (snapshotData?.projects || []).map(CardDataParser.parseProjectCard),
      volumes: hostNames.flatMap((hostName) => CardDataParser.parseVolumeCards(snapshotData.hosts[hostName]?.volumes, snapshotData.hosts[hostName])),
      disks: hostNames.flatMap((hostName) => CardDataParser.parseDiskCards(snapshotData.hosts[hostName]?.disks, snapshotData.hosts[hostName])),
      activity: CardDataParser.parseActivityCards(historyData),
      charts: hostNames.map((hostName) => CardDataParser.parseChartCards(chartsData, hostName)),
      metadata: {
        timestamp: snapshotData?.timestamp,
        lastUpdated: Date.now(),
        hasCompleteData: !!(snapshotData && historyData && chartsData),
      },
    };
  }

  /**
   * Get card statistics for performance monitoring
   * @param {Object} cardData - Card data to analyze
   * @returns {Object} Statistics about the card data
   */
  static getCardStatistics(cardData) {
    return {
      totalHosts: cardData.hosts?.length || 0,
      liveHosts: cardData.hosts?.filter((h) => h.isLive)?.length || 0,
      projects: cardData.projects?.length || 0,
      volumes: cardData.volumes?.length || 0,
      disks: cardData.disks?.length || 0,
      hasActivity: cardData.activity?.hasActivity || false,
      chartsLoaded: cardData.charts?.filter((c) => c.hasData)?.length || 0,
      completeness: CardDataParser.calculateCompleteness(cardData),
    };
  }

  /**
   * Calculate data completeness score
   * @param {Object} cardData - Card data to analyze
   */
  static calculateCompleteness(cardData) {
    const sections = [
      { key: "hosts", weight: 0.3, value: cardData.hosts?.filter((h) => h.hasTelemetry)?.length / Math.max(1, cardData.hosts?.length) },
      { key: "projects", weight: 0.2, value: Math.min(1, (cardData.projects?.filter((p) => p.hasData)?.length || 0) / 3) },
      { key: "activity", weight: 0.25, value: cardData.activity?.hasActivity ? 1 : 0 },
      { key: "charts", weight: 0.25, value: cardData.charts?.filter((c) => c.hasData)?.length / Math.max(1, cardData.charts?.length) },
    ];

    return sections.reduce((sum, section) => sum + (section.weight * section.value), 0) * 100;
  }

  /**
   * Validate and clean data before processing
   * @param {any} data - Raw data to validate
   * @param {string} dataType - Type of data
   * @returns {boolean} Whether data is valid
   */
  static validateDataIntegrity(data, dataType) {
    if (!data) return false;

    const validationRules = {
      hosts: (data) => Array.isArray(data?.hosts) && Object.keys(data.hosts).every((key) => data.hosts[key]),
      projects: (data) => Array.isArray(data?.projects),
      activity: (data) => data && typeof data === "object" && !Array.isArray(data),
      charts: (data) => data && typeof data === "object" && ["rates", "probes", "logs"].every((key) => key in data),
    };

    return validationRules[dataType]?.(data) || false;
  }
}

// Export for use in the dashboard application
if (typeof window !== "undefined") {
  window.CardDataParser = CardDataParser;
}

export default CardDataParser;