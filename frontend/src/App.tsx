import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import type { IconType } from 'react-icons'
import {
  Badge,
  Box,
  Button,
  Checkbox,
  Center,
  FormControl,
  FormLabel,
  Divider,
  Flex,
  Heading,
  HStack,
  Icon,
  Input,
  Popover,
  PopoverArrow,
  PopoverBody,
  PopoverCloseButton,
  PopoverContent,
  PopoverHeader,
  PopoverTrigger,
  Progress,
  Select,
  SimpleGrid,
  Spacer,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Spinner,
  Tr,
  Tag,
  TagLabel,
  useColorMode,
  useColorModeValue,
  useToast,
  Wrap,
  WrapItem,
  Switch,
} from '@chakra-ui/react'
import { FiGithub } from 'react-icons/fi'
import axios from 'axios'
import {
  FiActivity,
  FiArrowUp,
  FiArrowDown,
  FiDownload,
  FiFilter,
  FiCheckSquare,
  FiInfo,
  FiList,
  FiMoon,
  FiRefreshCw,
  FiSettings,
  FiSun,
  FiTrash2,
  FiStopCircle,
} from 'react-icons/fi'

type BackendSettings = {
  resume_downloads: boolean
  no_download: boolean
  download_all_versions: boolean
  organize_by_series: boolean
  specific_release: number | null
  thread_count: number
  verbose_logging: boolean
  http_max_connections: number
  http_max_connections_per_host: number
  http_total_timeout: number
  http_connect_timeout: number
  http_read_timeout: number
  retry_max_attempts: number
  retry_base_delay: number
  retry_max_delay: number
  scrapy_download_delay: number
  scrapy_concurrent_requests: number
  etsi_min_release: number
  web_max_log_messages: number
  web_refresh_interval: number
}

type FileRecord = {
  url: string
  series: string
  release: number
  ts_number: string
  version: string
  name?: string
}

type DownloadEvent = {
  timestamp: string
  filename: string
  status: string
  description: string
}

type FilesResponse = {
  total: number
  page: number
  page_size: number
  file_type: ApiState['current_file_type']
  items: FileRecord[]
}

type ViewPreferences = {
  pageSize: number
  orderBy: string | null
  direction: 'asc' | 'desc'
} 

type ApiState = {
  scraping_status: 'idle' | 'running' | 'completed' | 'error'
  download_status: 'idle' | 'running' | 'completed' | 'error'
  scraping_progress: number
  download_progress: number
  current_operation: string
  current_download_item?: string | null
  log_messages: string[]
  available_files: FileRecord[]
  current_file_type: 'none' | 'all' | 'filtered'
  completed_downloads: string[]
  failed_downloads: string[]
  recent_download_events: DownloadEvent[]
  last_update: number
  settings: BackendSettings
  app_version?: string
}

type Filters = {
  query: string
  series: string
  release: string
}

type BooleanSettingKey =
  | 'resume_downloads'
  | 'no_download'
  | 'download_all_versions'
  | 'organize_by_series'
  | 'verbose_logging'

const POLL_INTERVAL_MS = 5000
const PREFS_STORAGE_KEY = 'viewPrefs:v1'
const FILTERS_STORAGE_KEY = 'fileFilters:v1'
const DEFAULT_FILTERS: Filters = { query: '', series: '', release: '' }

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
})

type StatusKey = ApiState['scraping_status']

const statusMeta: Record<StatusKey, { label: string; color: string }> = {
  idle: { label: 'Idle', color: 'gray' },
  running: { label: 'Running', color: 'blue' },
  completed: { label: 'Completed', color: 'green' },
  error: { label: 'Error', color: 'red' },
}

function useApiState(): [ApiState | null, () => Promise<void>] {
  const toast = useToast()
  const [state, setState] = useState<ApiState | null>(null)

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<ApiState>('/state')
      setState(data)
    } catch (error) {
      console.error('Failed to load API state', error)
      toast({
        title: 'Cannot reach backend',
        description: 'Verify that the FastAPI server is running.',
        status: 'error',
        duration: 6000,
        isClosable: true,
      })
    }
  }, [toast])

  useEffect(() => {
    load()
    const handle = window.setInterval(load, POLL_INTERVAL_MS)
    return () => window.clearInterval(handle)
  }, [load])

  return [state, load]
}

function useViewPreferences(): [ViewPreferences, (prefs: Partial<ViewPreferences>) => void] {
  const defaultPrefs: ViewPreferences = {
    pageSize: 50,
    orderBy: 'ts_number',
    direction: 'asc',
  }
  const [prefs, setPrefs] = useState<ViewPreferences>(() => {
    try {
      const raw = localStorage.getItem(PREFS_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        return { ...defaultPrefs, ...parsed }
      }
    } catch (error) {
      console.warn('Failed to read view preferences', error)
    }
    return defaultPrefs
  })

  const update = useCallback((next: Partial<ViewPreferences>) => {
    setPrefs((prev) => {
      const merged = { ...prev, ...next }
      try {
        localStorage.setItem(PREFS_STORAGE_KEY, JSON.stringify(merged))
      } catch (error) {
        console.warn('Failed to persist view preferences', error)
      }
      return merged
    })
  }, [])

  return [prefs, update]
}

function StatusCard({
  title,
  status,
  progress,
  description,
  icon,
}: {
  title: string
  status: StatusKey
  progress: number
  description?: string
  icon: IconType
}) {
  const clamped = Math.max(0, Math.min(progress ?? 0, 100))
  const meta = statusMeta[status]
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const bg = useColorModeValue('white', 'gray.900')
  const iconColor = useColorModeValue('blue.500', 'blue.300')

  return (
    <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={5} bg={bg} shadow="sm">
      <HStack justify="space-between" mb={3}>
        <Heading size="sm">{title}</Heading>
        <Tag colorScheme={meta.color} size="sm">
          <TagLabel>{meta.label}</TagLabel>
        </Tag>
      </HStack>
      <HStack spacing={3} align="center">
        <Icon as={icon} boxSize={6} color={iconColor} />
        <Heading size="lg">{clamped.toFixed(0)}%</Heading>
      </HStack>
      <Progress value={clamped} size="sm" rounded="full" colorScheme={meta.color} mt={3} />
      {description ? (
        <Text fontSize="sm" color="gray.500" mt={2} noOfLines={2}>
          {description}
        </Text>
      ) : null}
    </Box>
  )
}

function FilesTable({
  files,
  selected,
  onToggle,
  onToggleAll,
  sortKey,
  sortDirection,
  onSort,
  isLoading,
  isAllSelected,
}: {
  files: FileRecord[]
  selected: string[]
  onToggle: (url: string) => void
  onToggleAll: (checked: boolean) => void
  sortKey: string | null
  sortDirection: 'asc' | 'desc'
  onSort: (key: string) => void
  isLoading: boolean
  isAllSelected: boolean
}) {
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const hoverBg = useColorModeValue('gray.50', 'whiteAlpha.100')
  const headerBg = useColorModeValue('white', 'gray.900')

  const renderSortIcon = (key: string) => {
    if (sortKey !== key) {
      return null
    }
    return <Icon as={sortDirection === 'asc' ? FiArrowUp : FiArrowDown} ml={2} boxSize={3} color="blue.400" />
  }

  if (isLoading) {
    return (
      <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={10} textAlign="center">
        <Center>
          <Spinner thickness="3px" speed="0.65s" emptyColor="gray.200" color="blue.400" size="lg" />
        </Center>
      </Box>
    )
  }

  if (!files.length) {
    return (
      <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={6} textAlign="center" color="gray.500">
        No files match your filters. Run a scrape or adjust filters.
      </Box>
    )
  }
  return (
    <Box borderWidth="1px" borderColor={borderColor} rounded="lg" overflow="hidden">
      <Box maxH="520px" overflowY="auto">
        <Table size="sm" variant="simple">
          <Thead position="sticky" top={0} bg={headerBg}>
            <Tr>
              <Th width="52px">
                <Checkbox
                  isChecked={isAllSelected}
                  isIndeterminate={!isAllSelected && selected.length > 0}
                  onChange={(event) => onToggleAll(event.target.checked)}
                  aria-label="Select all"
                />
              </Th>
              <Th cursor="pointer" onClick={() => onSort('ts_number')}>
                <Flex align="center">
                  TS
                  {renderSortIcon('ts_number')}
                </Flex>
              </Th>
              <Th cursor="pointer" onClick={() => onSort('version')}>
                <Flex align="center">
                  Version
                  {renderSortIcon('version')}
                </Flex>
              </Th>
              <Th cursor="pointer" onClick={() => onSort('series')}>
                <Flex align="center">
                  Series
                  {renderSortIcon('series')}
                </Flex>
              </Th>
              <Th isNumeric cursor="pointer" onClick={() => onSort('release')}>
                <Flex align="center" justify="flex-end">
                  Release
                  {renderSortIcon('release')}
                </Flex>
              </Th>
              <Th>URL</Th>
            </Tr>
          </Thead>
          <Tbody>
            {files.map((item) => {
              const checked = selected.includes(item.url)
              return (
                <Tr key={item.url} _hover={{ bg: hoverBg }}>
                  <Td>
                    <Checkbox isChecked={checked} onChange={() => onToggle(item.url)} />
                  </Td>
                  <Td fontFamily="mono">{item.ts_number}</Td>
                  <Td>{item.version}</Td>
                  <Td>{item.series}</Td>
                  <Td isNumeric>{item.release}</Td>
                  <Td maxW="360px" overflow="hidden" textOverflow="ellipsis">
                    <a href={item.url} target="_blank" rel="noreferrer">
                      {item.url}
                    </a>
                  </Td>
                </Tr>
              )
            })}
          </Tbody>
        </Table>
      </Box>
    </Box>
  )
}

function LogsPanel({
  logs,
  onClear,
  autoScroll,
  onToggleAutoScroll,
}: {
  logs: string[]
  onClear: () => Promise<void>
  autoScroll: boolean
  onToggleAutoScroll: (next: boolean) => void
}) {
  const toast = useToast()
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const bg = useColorModeValue('white', 'gray.900')
  const scrollBg = useColorModeValue('gray.50', 'blackAlpha.300')
  const scrollRef = useRef<HTMLDivElement>(null)

  const handleClear = async () => {
    try {
      await onClear()
      toast({ title: 'Logs cleared', status: 'success', duration: 2000, isClosable: true })
    } catch (error) {
      console.error('Failed to clear logs', error)
      toast({ title: 'Failed to clear logs', status: 'error', duration: 4000, isClosable: true })
    }
  }

  useEffect(() => {
    if (!autoScroll) return
    const node = scrollRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [logs, autoScroll])

  return (
    <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={4} bg={bg} shadow="sm">
      <HStack justify="space-between" mb={3}>
        <Heading size="sm">Activity Log</Heading>
        <HStack spacing={3}>
          <FormControl display="flex" alignItems="center" width="auto">
            <FormLabel htmlFor="logs-autoscroll" mb="0" fontSize="sm" color="gray.500">
              Auto-scroll
            </FormLabel>
            <Switch
              id="logs-autoscroll"
              size="sm"
              isChecked={autoScroll}
              onChange={(event) => onToggleAutoScroll(event.target.checked)}
            />
          </FormControl>
          <Button leftIcon={<FiTrash2 />} size="sm" variant="outline" onClick={handleClear}>
            Clear
          </Button>
        </HStack>
      </HStack>
      <Box
        ref={scrollRef}
        bg={scrollBg}
        rounded="md"
        p={3}
        maxH="260px"
        overflowY="auto"
        fontFamily="mono"
        fontSize="sm"
      >
        {logs.length === 0 ? (
          <Text color="gray.500">No log messages yet.</Text>
        ) : (
          <Stack spacing={1}>
            {logs.map((line) => (
              <Text key={line}>{line}</Text>
            ))}
          </Stack>
        )}
      </Box>
    </Box>
  )
}

function SettingsPanel({
  settings,
  onSave,
}: {
  settings: BackendSettings
  onSave: (patch: Partial<BackendSettings>) => Promise<void>
}) {
  const toast = useToast()
  const [form, setForm] = useState(settings)

  useEffect(() => {
    setForm(settings)
  }, [settings])

  const toggleFlag = (key: BooleanSettingKey) => async () => {
    const previous = form[key]
    const nextValue = !previous
    setForm((prev) => ({ ...prev, [key]: nextValue }))
    try {
      await onSave({ [key]: nextValue } as Partial<BackendSettings>)
      toast({ title: 'Settings updated', status: 'success', duration: 2000, isClosable: true })
    } catch (error) {
      console.error('Failed to update setting', error)
      toast({ title: 'Failed to update setting', status: 'error', duration: 4000, isClosable: true })
      setForm((prev) => ({ ...prev, [key]: previous }))
    }
  }

  const updateThreads = async (value: string) => {
    const parsed = Number.parseInt(value, 10)
    const fallback = Number.isNaN(parsed) ? form.thread_count : parsed
    const nextValue = Math.max(1, Math.min(fallback, 64))
    setForm((prev) => ({ ...prev, thread_count: nextValue }))
    try {
      await onSave({ thread_count: nextValue })
    } catch (error) {
      console.error('Failed to update thread count', error)
      toast({ title: 'Failed to update thread count', status: 'error', duration: 4000, isClosable: true })
      setForm((prev) => ({ ...prev, thread_count: form.thread_count }))
    }
  }

  const updateRelease = async (value: string) => {
    const nextValue = value === '' ? null : Number.parseInt(value, 10)
    setForm((prev) => ({ ...prev, specific_release: nextValue }))
    try {
      await onSave({ specific_release: nextValue })
    } catch (error) {
      console.error('Failed to update release filter', error)
      toast({ title: 'Failed to update release filter', status: 'error', duration: 4000, isClosable: true })
      setForm((prev) => ({ ...prev, specific_release: form.specific_release }))
    }
  }

  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const bg = useColorModeValue('white', 'gray.900')

  return (
    <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={4} bg={bg} shadow="sm">
      <HStack spacing={3} mb={4}>
        <Icon as={FiSettings} />
        <Heading size="sm">Runtime Settings</Heading>
      </HStack>
      <Stack spacing={3}>
        <Checkbox isChecked={form.resume_downloads} onChange={toggleFlag('resume_downloads')}>
          Resume downloads when possible
        </Checkbox>
        <Checkbox isChecked={form.no_download} onChange={toggleFlag('no_download')}>
          Prepare metadata only (skip downloads)
        </Checkbox>
        <Checkbox isChecked={form.download_all_versions} onChange={toggleFlag('download_all_versions')}>
          Download all available versions
        </Checkbox>
        <Checkbox isChecked={form.organize_by_series} onChange={toggleFlag('organize_by_series')}>
          Organize downloads by series hierarchy
        </Checkbox>
        <Checkbox isChecked={form.verbose_logging} onChange={toggleFlag('verbose_logging')}>
          Verbose logging
        </Checkbox>
        <Flex gap={3} align="center">
          <Text fontSize="sm" color="gray.500">
            Worker threads
          </Text>
          <Input
            width="100px"
            type="number"
            min={1}
            max={64}
            value={form.thread_count}
            onChange={(event) => updateThreads(event.target.value)}
          />
        </Flex>
        <Flex gap={3} align="center">
          <Text fontSize="sm" color="gray.500">
            Specific release
          </Text>
          <Input
            width="120px"
            placeholder="e.g. 18"
            value={form.specific_release ?? ''}
            onChange={(event) => updateRelease(event.target.value)}
          />
        </Flex>
      </Stack>
    </Box>
  )
}

function ActionButtons({
  state,
  refresh,
  selected,
  fileType,
}: {
  state: ApiState
  refresh: () => Promise<void>
  selected: string[]
  fileType: ApiState['current_file_type']
}) {
  const toast = useToast()

  const startScrape = async () => {
    try {
      await api.post('/scrape')
      toast({ title: 'Scrape started', status: 'info', duration: 2000, isClosable: true })
      await refresh()
    } catch (error) {
      console.error('Failed to start scrape', error)
      toast({ title: 'Failed to start scrape', status: 'error', duration: 4000, isClosable: true })
    }
  }

  const forceScrape = async () => {
    try {
      await api.post('/scrape', { force: true })
      toast({ title: 'Forced scrape triggered', status: 'info', duration: 2000, isClosable: true })
      await refresh()
    } catch (error) {
      console.error('Failed to force scrape', error)
      toast({ title: 'Force scrape request failed', status: 'error', duration: 4000, isClosable: true })
    }
  }

  const toggleFilter = async (event: ChangeEvent<HTMLInputElement>) => {
    const shouldFilter = event.target.checked
    try {
      if (shouldFilter) {
        await api.post('/filter')
        toast({ title: 'Filtering to latest versions…', status: 'info', duration: 2000, isClosable: true })
      } else {
        await api.post('/filter', { clear: true })
        toast({ title: 'Showing all versions', status: 'info', duration: 2000, isClosable: true })
      }
      await refresh()
    } catch (error) {
      console.error('Filter request failed', error)
      toast({ title: 'Filter request failed', status: 'error', duration: 4000, isClosable: true })
    }
  }

  const startDownload = async () => {
    if (!selected.length) {
      toast({ title: 'Select at least one file', status: 'warning', duration: 3000, isClosable: true })
      return
    }
    try {
      await api.post('/download', { urls: selected })
      toast({ title: `Queued ${selected.length} file(s)`, status: 'success', duration: 2000, isClosable: true })
      await refresh()
    } catch (error) {
      console.error('Download failed to start', error)
      toast({ title: 'Download failed to start', status: 'error', duration: 4000, isClosable: true })
    }
  }

  const stopDownload = async () => {
    try {
      await api.post('/download/stop')
      toast({ title: 'Cancelling downloads…', status: 'warning', duration: 2000, isClosable: true })
      await refresh()
    } catch (error) {
      console.error('Failed to stop download', error)
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        toast({ title: 'No active download to stop', status: 'info', duration: 2000, isClosable: true })
      } else {
        toast({ title: 'Failed to stop download', status: 'error', duration: 4000, isClosable: true })
      }
    }
  }

  const reloadFiles = async () => {
    try {
      await api.post('/files/reload')
      toast({ title: 'File catalogue refreshed', status: 'success', duration: 2000, isClosable: true })
      await refresh()
    } catch (error) {
      console.error('Failed to reload files', error)
      toast({ title: 'Failed to reload files', status: 'error', duration: 4000, isClosable: true })
    }
  }

  return (
    <Wrap spacing={3}>
      <WrapItem>
        <Button
          leftIcon={<FiActivity />}
          colorScheme="blue"
          onClick={startScrape}
          isDisabled={state.scraping_status === 'running'}
        >
          Start Scraping
        </Button>
      </WrapItem>
      <WrapItem>
        <Button
          leftIcon={<FiRefreshCw />}
          colorScheme="orange"
          onClick={forceScrape}
          isDisabled={state.scraping_status === 'running'}
        >
          Force Scrape (rebuild links.json)
        </Button>
      </WrapItem>
      <WrapItem>
        <Checkbox
          size="lg"
          colorScheme="blue"
          isChecked={fileType === 'filtered'}
          isDisabled={state.scraping_status === 'running'}
          onChange={toggleFilter}
        >
          <HStack spacing={2}>
            <Icon as={FiFilter} />
            <Text>Latest versions only</Text>
          </HStack>
        </Checkbox>
      </WrapItem>
      <WrapItem>
        <Button
          leftIcon={<FiDownload />}
          colorScheme="green"
          onClick={startDownload}
          isDisabled={state.download_status === 'running'}
        >
          Download Selected
        </Button>
      </WrapItem>
      {state.download_status === 'running' ? (
        <WrapItem>
          <Button leftIcon={<FiStopCircle />} colorScheme="red" onClick={stopDownload}>
            Stop Download
          </Button>
        </WrapItem>
      ) : null}
      <WrapItem>
        <Button leftIcon={<FiRefreshCw />} colorScheme="teal" onClick={reloadFiles}>
          Reload Files
        </Button>
      </WrapItem>
    </Wrap>
  )
}

function FileFilters({
  filters,
  onChange,
  available,
}: {
  filters: Filters
  onChange: (next: Filters) => void
  available: FileRecord[]
}) {
  const seriesOptions = useMemo(() => {
    const set = new Set<string>()
    available.forEach((file) => {
      if (file.series) set.add(file.series)
    })
    return Array.from(set).sort()
  }, [available])

  const releaseOptions = useMemo(() => {
    const set = new Set<number>()
    available.forEach((file) => {
      if (typeof file.release === 'number') set.add(file.release)
    })
    return Array.from(set).sort((a, b) => a - b)
  }, [available])

  return (
    <HStack spacing={4} flexWrap="wrap" align="flex-end">
      <Flex direction="column" minW="220px">
        <Text fontSize="sm" color="gray.500">
          Search
        </Text>
        <Input
          placeholder="Search by TS or URL"
          value={filters.query}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
        />
      </Flex>
      <Flex direction="column" minW="160px">
        <Text fontSize="sm" color="gray.500">
          Series
        </Text>
        <Select value={filters.series} onChange={(event) => onChange({ ...filters, series: event.target.value })}>
          <option value="">All</option>
          {seriesOptions.map((series) => (
            <option key={series} value={series}>
              {series}
            </option>
          ))}
        </Select>
      </Flex>
      <Flex direction="column" minW="160px">
        <Text fontSize="sm" color="gray.500">
          Release
        </Text>
        <Select value={filters.release} onChange={(event) => onChange({ ...filters, release: event.target.value })}>
          <option value="">All</option>
          {releaseOptions.map((release) => (
            <option key={release} value={String(release)}>
              {release}
            </option>
          ))}
        </Select>
      </Flex>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onChange({ ...DEFAULT_FILTERS })}
        leftIcon={<FiRefreshCw />}
      >
        Reset filters
      </Button>
    </HStack>
  )
}

function SelectedFilesCard({
  items,
  onRemove,
  onClear,
}: {
  items: { url: string; label: string; meta?: string; fullUrl: string }[]
  onRemove: (url: string) => void
  onClear: () => void
}) {
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const bg = useColorModeValue('white', 'gray.900')
  const scrollBg = useColorModeValue('gray.50', 'blackAlpha.300')

  return (
    <Box borderWidth="1px" borderColor={borderColor} rounded="lg" p={4} bg={bg} shadow="sm">
      <HStack spacing={3} mb={4} align="center" justify="space-between">
        <HStack spacing={3} align="center">
          <Icon as={FiCheckSquare} />
          <Heading size="sm">Selected Files</Heading>
        </HStack>
        <Badge colorScheme={items.length ? 'blue' : 'gray'}>{items.length}</Badge>
      </HStack>
      {items.length === 0 ? (
        <Text color="gray.500">No files selected.</Text>
      ) : (
        <Stack spacing={3}>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<FiTrash2 />}
            onClick={onClear}
            alignSelf="flex-start"
          >
            Clear all
          </Button>
          <Box
            borderWidth="1px"
            borderColor={borderColor}
            rounded="md"
            bg={scrollBg}
            maxH="260px"
            overflowY="auto"
            px={3}
            py={2}
          >
            <Stack spacing={3}>
              {items.map((item) => (
                <Flex key={item.url} align="flex-start" justify="space-between" gap={3} minH="44px">
                  <Box flex="1" minW={0}>
                    <Text fontWeight="semibold" noOfLines={1}>
                      {item.label}
                    </Text>
                    <Text fontSize="xs" color="gray.500" noOfLines={1}>
                      {item.meta ?? item.fullUrl}
                    </Text>
                  </Box>
                  <Button size="xs" variant="outline" onClick={() => onRemove(item.url)}>
                    Remove
                  </Button>
                </Flex>
              ))}
            </Stack>
          </Box>
        </Stack>
      )}
    </Box>
  )
}

function formatDownloadTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return 'Unknown time'
  const parsed = Date.parse(timestamp)
  if (!Number.isNaN(parsed)) {
    return new Date(parsed).toLocaleString(undefined, {
      dateStyle: 'short',
      timeStyle: 'medium',
    })
  }
  const parts = timestamp.split(':').map((segment) => Number.parseInt(segment, 10))
  if (parts.length >= 3 && parts.every((value) => Number.isFinite(value))) {
    const [hours, minutes, seconds] = parts
    const base = new Date()
    base.setHours(hours, minutes, seconds, 0)
    return base.toLocaleTimeString()
  }
  return timestamp
}

function DownloadEvents({
  events,
  autoScroll,
  onToggleAutoScroll,
}: {
  events: DownloadEvent[]
  autoScroll: boolean
  onToggleAutoScroll: (next: boolean) => void
}) {
  const borderColor = useColorModeValue('gray.200', 'whiteAlpha.200')
  const bg = useColorModeValue('white', 'gray.900')
  const itemBorderColor = useColorModeValue('gray.100', 'whiteAlpha.100')
  const statusColor = (status: string) => {
    const lower = status.toLowerCase()
    if (lower.includes('fail') || lower.includes('error')) return 'red'
    if (lower.includes('success') || lower.includes('complete')) return 'green'
    return 'blue'
  }
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!autoScroll) return
    const node = scrollRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [events, autoScroll])

  return (
    <Box
      borderWidth="1px"
      borderColor={borderColor}
      rounded="lg"
      p={4}
      bg={bg}
      shadow="sm"
      display="flex"
      flexDirection="column"
      height="100%"
      minH="320px"
    >
      <HStack spacing={3} mb={4} justify="space-between" align="center" flexShrink={0}>
        <HStack spacing={3}>
          <Icon as={FiList} />
          <Heading size="sm">Recent Download Events</Heading>
        </HStack>
        <FormControl display="flex" alignItems="center" width="auto">
          <FormLabel htmlFor="events-autoscroll" mb="0" fontSize="sm" color="gray.500">
            Auto-scroll
          </FormLabel>
          <Switch
            id="events-autoscroll"
            size="sm"
            isChecked={autoScroll}
            onChange={(event) => onToggleAutoScroll(event.target.checked)}
          />
        </FormControl>
      </HStack>
      {events.length === 0 ? (
        <Center flex="1" color="gray.500">
          No download events yet.
        </Center>
      ) : (
        <Stack
          ref={scrollRef}
          spacing={3}
          flex="1"
          overflowY="auto"
          pr={1}
        >
          {events.map((event) => (
            <Box key={`${event.timestamp}-${event.filename}`} borderWidth="1px" borderColor={itemBorderColor} rounded="md" p={3}>
              <HStack spacing={3} align="flex-start">
                <Badge colorScheme={statusColor(event.status)}>{event.status}</Badge>
                <Stack spacing={0} flex="1">
                  <Text fontWeight="semibold" noOfLines={1}>
                    {event.filename}
                  </Text>
                  <Text fontSize="sm" color="gray.500" noOfLines={2}>
                    {event.description || 'No description'}
                  </Text>
                  <Text fontSize="xs" color="gray.400">
                    {formatDownloadTimestamp(event.timestamp)}
                  </Text>
                </Stack>
              </HStack>
            </Box>
          ))}
        </Stack>
      )}
    </Box>
  )
}

function App() {
  const { colorMode, toggleColorMode } = useColorMode()
  const buildVersion = import.meta.env.VITE_APP_VERSION ?? __APP_VERSION__
  const currentYear = new Date().getFullYear()
  const [state, refresh] = useApiState()
  const appVersion = state?.app_version?.trim() ? state.app_version : buildVersion
  const [selected, setSelected] = useState<string[]>([])
  const [filters, setFilters] = useState<Filters>(() => {
    if (typeof window === 'undefined') {
      return { ...DEFAULT_FILTERS }
    }
    try {
      const raw = window.localStorage.getItem(FILTERS_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        return {
          query: typeof parsed.query === 'string' ? parsed.query : '',
          series: typeof parsed.series === 'string' ? parsed.series : '',
          release: typeof parsed.release === 'string' ? parsed.release : '',
        }
      }
    } catch (error) {
      console.warn('Failed to read saved filters', error)
    }
    return { ...DEFAULT_FILTERS }
  })

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    try {
      window.localStorage.setItem(FILTERS_STORAGE_KEY, JSON.stringify(filters))
    } catch (error) {
      console.warn('Failed to persist filters', error)
    }
  }, [filters])
  const [prefs, setPrefs] = useViewPreferences()
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [fileType, setFileType] = useState<ApiState['current_file_type']>('none')
  const [pagedFiles, setPagedFiles] = useState<FileRecord[]>([])
  const [isLoadingFiles, setIsLoadingFiles] = useState(false)
  const [logAutoScroll, setLogAutoScroll] = useState(true)
  const [eventAutoScroll, setEventAutoScroll] = useState(true)

  useEffect(() => {
    if (!state) return
    const urls = new Set(state.available_files.map((file) => file.url))
    setSelected((prev) => prev.filter((url) => urls.has(url)))
  }, [state])

  const selectedSummaries = useMemo(() => {
    if (!state) return []
    const lookup = new Map(state.available_files.map((file) => [file.url, file]))
    return selected.map((url) => {
      const record = lookup.get(url)
      const label = record?.ts_number
        ? `${record.ts_number}${record?.version ? ` · v${record.version}` : ''}`
        : record?.name ?? url.split('/').slice(-1)[0]
      const metaParts: string[] = []
      if (record?.series) metaParts.push(`Series ${record.series}`)
      if (typeof record?.release === 'number' && !Number.isNaN(record.release)) {
        metaParts.push(`Release ${record.release}`)
      }
      return {
        url,
        label,
        meta: metaParts.join(' · ') || undefined,
        fullUrl: url,
      }
    })
  }, [selected, state])

  const handleToggleAll = useCallback(
    (checked: boolean, scope: FileRecord[] | 'all') => {
      setSelected((prev) => {
        if (checked) {
          if (scope === 'all' && state) {
            return Array.from(new Set([...prev, ...state.available_files.map((file) => file.url)]))
          }
          if (Array.isArray(scope)) {
            return Array.from(new Set([...prev, ...scope.map((file) => file.url)]))
          }
        }

        if (scope === 'all' && state) {
          const remove = new Set(state.available_files.map((file) => file.url))
          return prev.filter((url) => !remove.has(url))
        }

        if (Array.isArray(scope)) {
          const remove = new Set(scope.map((file) => file.url))
          return prev.filter((url) => !remove.has(url))
        }

        return prev
      })
    },
    [state],
  )

  useEffect(() => {
    let ignore = false
    const loadPage = async () => {
      if (!ignore) {
        setIsLoadingFiles(true)
      }
      try {
        const { data } = await api.post<FilesResponse>('/files', {
          page,
          page_size: prefs.pageSize,
          order_by: prefs.orderBy,
          direction: prefs.direction,
          query: filters.query || null,
          series: filters.series || null,
          release: filters.release ? Number(filters.release) : null,
        })
        if (!ignore) {
          if (page > 1 && data.items.length === 0 && data.total > 0) {
            setPage(1)
            return
          }
          setPagedFiles(data.items)
          setTotal(data.total)
          setFileType(data.file_type)
        }
      } catch (error) {
        console.error('Failed to load files page', error)
      } finally {
        if (!ignore) {
          setIsLoadingFiles(false)
        }
      }
    }
    loadPage()
    return () => {
      ignore = true
    }
  }, [page, prefs.pageSize, prefs.orderBy, prefs.direction, filters.query, filters.series, filters.release, state?.last_update])

  useEffect(() => {
    setPage(1)
  }, [filters, prefs.orderBy, prefs.pageSize, prefs.direction])

  const toggleSelection = (url: string) => {
    setSelected((prev) => (prev.includes(url) ? prev.filter((item) => item !== url) : [...prev, url]))
  }

  const removeSelection = (url: string) => {
    setSelected((prev) => prev.filter((item) => item !== url))
  }

  const handleSort = (key: string) => {
    const isSame = prefs.orderBy === key
    const nextDirection = isSame && prefs.direction === 'asc' ? 'desc' : 'asc'
    setPrefs({ orderBy: key, direction: nextDirection })
  }

  const clearLogs = async () => {
    await api.post('/logs/clear')
    await refresh()
  }

  const saveSettings = async (patch: Partial<BackendSettings>) => {
    await api.patch('/settings', patch)
    await refresh()
  }

  const bg = useColorModeValue('gray.100', 'gray.800')
  const cardBg = useColorModeValue('white', 'gray.900')
  const cardBorder = useColorModeValue('gray.200', 'whiteAlpha.200')

  if (!state) {
    return (
      <Flex minH="100vh" align="center" justify="center" bg={bg}>
        <Stack spacing={4} align="center">
          <Icon as={FiRefreshCw} boxSize={8} />
          <Text>Loading dashboard…</Text>
        </Stack>
      </Flex>
    )
  }

  return (
    <Box minH="100vh" bg={bg} px={[4, 6, 10]} py={6}>
      <Stack spacing={6} maxW="1200px" mx="auto">
        <Flex align="center" gap={4}>
          <Box>
            <Stack spacing={1}>
              <Heading size="lg">3GPP Downloader Control Center</Heading>
              <Text color="gray.500" fontSize="xs">
                Version: {appVersion}
              </Text>
              <Text color="gray.500" fontSize="sm">
                Orchestrate scraping, filtering, and downloads powered by FastAPI + Chakra UI
              </Text>
            </Stack>
          </Box>
          <Spacer />
          <Popover placement="bottom-end">
            <PopoverTrigger>
              <Button leftIcon={<FiInfo />} variant="outline">
                Help
              </Button>
            </PopoverTrigger>
            <PopoverContent maxW="sm">
              <PopoverArrow />
              <PopoverCloseButton />
              <PopoverHeader fontWeight="semibold">Quick tour</PopoverHeader>
              <PopoverBody>
                <Stack spacing={2} fontSize="sm" lineHeight="1.4">
                  <Text>Monitor scrape and download progress with the status cards.</Text>
                  <Text>Use the action bar to trigger scraping, filtering, downloads, or cancellation.</Text>
                  <Text>Adjust runtime settings to change downloader behavior; updates persist across sessions.</Text>
                  <Text>Inspect logs and recent download events to troubleshoot issues quickly.</Text>
                </Stack>
              </PopoverBody>
            </PopoverContent>
          </Popover>
          <Button as="a" href="https://github.com/tekgnosis-net/3gpp-downloader" target="_blank" leftIcon={<FiGithub />} variant="ghost" mr={2}>
            Repo
          </Button>
          <Button leftIcon={colorMode === 'dark' ? <FiSun /> : <FiMoon />} onClick={toggleColorMode} variant="outline">
            {colorMode === 'dark' ? 'Light mode' : 'Dark mode'}
          </Button>
        </Flex>

        <SimpleGrid columns={[1, null, 2]} spacing={4}>
          <StatusCard
            title="Scraping"
            status={state.scraping_status}
            progress={state.scraping_progress}
            description={state.current_operation}
            icon={FiActivity}
          />
          <StatusCard
            title="Download"
            status={state.download_status}
            progress={state.download_progress}
            description={state.current_download_item || state.current_operation}
            icon={FiDownload}
          />
        </SimpleGrid>

  <ActionButtons state={state} refresh={refresh} selected={selected} fileType={fileType} />

        <SimpleGrid columns={[1, null, 2]} spacing={4}>
          <LogsPanel
            logs={state.log_messages}
            onClear={clearLogs}
            autoScroll={logAutoScroll}
            onToggleAutoScroll={(next) => setLogAutoScroll(next)}
          />
          <SettingsPanel settings={state.settings} onSave={saveSettings} />
        </SimpleGrid>

        <SimpleGrid columns={[1, null, 2]} spacing={4}>
          <Box borderWidth="1px" borderColor={cardBorder} rounded="lg" p={4} bg={cardBg} shadow="sm">
            <HStack mb={3} spacing={4} align="center">
              <Icon as={FiList} />
              <Heading size="sm">Available Files</Heading>
              <Badge colorScheme={fileType === 'filtered' ? 'green' : 'gray'}>
                {fileType === 'filtered' ? 'Latest versions' : 'All entries'}
              </Badge>
              <Spacer />
              <Text fontSize="sm" color="gray.500">
                Showing {pagedFiles.length} of {total} files (page {page})
              </Text>
            </HStack>
            <Stack spacing={4}>
              <HStack justify="space-between" align="center">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleToggleAll(true, 'all')}
                  isDisabled={!state || state.available_files.length === 0}
                >
                  Select all {total} files
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleToggleAll(false, 'all')}
                  isDisabled={selected.length === 0}
                >
                  Clear selection
                </Button>
              </HStack>
              <FileFilters filters={filters} onChange={setFilters} available={state.available_files} />
              <Text fontSize="sm" color="gray.500">
                Selected files: {selected.length}
              </Text>
              <FilesTable
                files={pagedFiles}
                selected={selected}
                onToggle={toggleSelection}
                onToggleAll={(checked) => handleToggleAll(checked, pagedFiles)}
                sortKey={prefs.orderBy}
                sortDirection={prefs.direction}
                onSort={handleSort}
                isLoading={isLoadingFiles}
                isAllSelected={pagedFiles.length > 0 && pagedFiles.every((file) => selected.includes(file.url))}
              />
              <HStack justify="space-between" mt={2}>
                <HStack>
                  <Button size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} isDisabled={page <= 1}>
                    Prev
                  </Button>
                  <Button size="sm" onClick={() => setPage((p) => p + 1)} isDisabled={page * prefs.pageSize >= total}>
                    Next
                  </Button>
                  <Text fontSize="sm" color="gray.500">
                    Page {page} · {Math.min(page * prefs.pageSize, total)} / {total}
                  </Text>
                </HStack>
                <HStack>
                  <Text fontSize="sm" color="gray.500">
                    Page size
                  </Text>
                  <Select
                    size="sm"
                    width="120px"
                    value={String(prefs.pageSize)}
                    onChange={(e) => {
                      setPrefs({ pageSize: Number(e.target.value) })
                    }}
                  >
                    {[10, 25, 50, 100].map((n) => (
                      <option key={n} value={String(n)}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </HStack>
              </HStack>
            </Stack>
          </Box>
          <DownloadEvents
            events={state.recent_download_events}
            autoScroll={eventAutoScroll}
            onToggleAutoScroll={(next) => setEventAutoScroll(next)}
          />
        </SimpleGrid>

        <SelectedFilesCard
          items={selectedSummaries}
          onRemove={removeSelection}
          onClear={() => handleToggleAll(false, 'all')}
        />

        <Box textAlign="center" color="gray.500" fontSize="sm" mt={8}>
          <Divider mb={4} />
          <Text>
            Backend last update: {new Date(state.last_update * 1000).toLocaleTimeString()} · Completed downloads: {state.completed_downloads.length} ·
            Failed downloads: {state.failed_downloads.length}
          </Text>
          <Text mt={2} fontSize="xs">
            © {currentYear} Tekgnosis Pty Ltd
          </Text>
        </Box>
      </Stack>
    </Box>
  )
}

export default App
