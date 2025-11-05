import { extendTheme } from '@chakra-ui/react'
import type { ThemeConfig } from '@chakra-ui/react'

const config: ThemeConfig = {
  initialColorMode: 'light',
  useSystemColorMode: false,
};

const theme = extendTheme({
  config,
  styles: {
    global: {
      body: {
        bg: 'gray.50',
        color: 'gray.800',
        _dark: {
          bg: 'gray.900',
          color: 'whiteAlpha.900',
        },
      },
    },
  },
  fonts: {
    heading: `'Inter', system-ui, sans-serif`,
    body: `'Inter', system-ui, sans-serif`,
  },
  semanticTokens: {
    colors: {
      brand: {
        default: 'blue.500',
        _dark: 'blue.300',
      },
    },
  },
})

export default theme
