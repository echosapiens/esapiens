import { createTheme, type MantineColorsTuple } from '@mantine/core';

/* ─── Custom Professional Color Palette ─── */
const brand: MantineColorsTuple = [
  '#FAFAFA', // 0 - lightest
  '#F5F5F5', // 1
  '#E5E5E5', // 2
  '#D4D4D4', // 3
  '#A3A3A3', // 4
  '#737373', // 5
  '#525252', // 6
  '#3A3A3A', // 7
  '#1A3A3C', // 8
  '#092426', // 9 - darkest (primary)
];

/* ─── Professional Light Theme for E.sapiens ─── */
export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: 9,

  colors: {
    brand,
  },

  /* Typography — Inter headings & body, Roboto Mono code */
  fontFamily: "var(--e-font-sans)",
  fontFamilyMonospace: "var(--e-font-mono)",

  headings: {
    fontFamily: "var(--e-font-display)",
    fontWeight: '600',
    sizes: {
      h1: { fontSize: 'var(--e-type-2xl)', lineHeight: '1.25' },   /* 28px */
      h2: { fontSize: 'var(--e-type-xl)', lineHeight: '1.3' },     /* 24px */
      h3: { fontSize: 'var(--e-type-lg)', lineHeight: '1.35' },     /* 20px */
      h4: { fontSize: 'var(--e-type-base)', lineHeight: '1.4' },    /* 16px */
      h5: { fontSize: 'var(--e-type-sm)', fontWeight: '600' },      /* 14px */
      h6: { fontSize: 'var(--e-type-xs)', fontWeight: '600' },     /* 12px */
    },
  },

  fontSizes: {
    xs: 'var(--e-type-xs)',      /* 12px */
    sm: 'var(--e-type-sm)',      /* 14px */
    md: 'var(--e-type-base)',    /* 16px */
    lg: 'var(--e-type-md)',      /* 18px */
    xl: 'var(--e-type-lg)',      /* 20px */
  },

  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '0.75rem',
    lg: '1rem',
    xl: '1.25rem',
  },

  radius: {
    xs: '4px',
    sm: '4px',
    md: '6px',
    lg: '8px',
    xl: '12px',
  },

  defaultRadius: 'md',
  cursorType: 'pointer',
  respectReducedMotion: true,

  /* ─── Component Overrides ─── */
  components: {
    AppShell: {
      styles: {
        main: {
          backgroundColor: 'var(--e-bg-base)',
          minHeight: '100vh',
        },
      },
    },

    Paper: {
      defaultProps: {
        p: 'md',
        radius: 'md',
      },
      styles: {
        root: {
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border-subtle)',
          boxShadow: 'var(--e-shadow-sm)',
        },
      },
    },

    Card: {
      defaultProps: {
        p: 'lg',
        radius: 'md',
        withBorder: true,
      },
      styles: {
        root: {
          backgroundColor: 'var(--e-bg-surface)',
          borderColor: 'var(--e-border-subtle)',
          transition: 'box-shadow 0.15s ease, border-color 0.15s ease',
        },
      },
    },

    Button: {
      defaultProps: {
        radius: 'md',
        size: 'sm',
      },
      styles: {
        root: {
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          fontWeight: '500',
          transition: 'all 0.15s ease',
          height: '36px',
        },
      },
    },

    ActionIcon: {
      defaultProps: {
        radius: 'md',
        variant: 'subtle',
      },
      styles: {
        root: {
          transition: 'all 0.1s ease',
        },
      },
    },

    TextInput: {
      defaultProps: {
        radius: 'md',
        size: 'sm',
      },
      styles: {
        input: {
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border)',
          color: 'var(--e-text-primary)',
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          padding: '8px 12px',
          height: '36px',
          transition: 'border-color 0.1s ease, box-shadow 0.1s ease',
          '&:focus': {
            borderColor: 'var(--e-brand)',
            boxShadow: '0 0 0 3px rgba(9, 36, 38, 0.08)',
          },
          '&::placeholder': {
            color: 'var(--e-text-muted)',
          },
        },
      },
    },

    Badge: {
      defaultProps: {
        radius: 'sm',
        variant: 'light',
      },
      styles: {
        root: {
          fontFamily: 'var(--e-font-mono)',
          fontSize: 'var(--e-type-xs)',
          fontWeight: '500',
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          padding: '3px 8px',
          height: 'auto',
        },
      },
    },

    Tooltip: {
      defaultProps: {
        withArrow: true,
        arrowSize: 6,
        radius: 'sm',
      },
      styles: {
        tooltip: {
          fontFamily: 'var(--e-font-mono)',
          fontSize: 'var(--e-type-xs)',
          fontWeight: '500',
          letterSpacing: '0.03em',
          padding: '6px 10px',
          backgroundColor: '#092426',
        },
      },
    },

    Modal: {
      defaultProps: {
        radius: 'lg',
        centered: true,
      },
      styles: {
        header: {
          fontFamily: 'var(--e-font-display)',
          fontWeight: '600',
        },
        body: {
          fontFamily: 'var(--e-font-sans)',
        },
      },
    },

    NavLink: {
      styles: {
        root: {
          borderRadius: 'var(--e-radius-md)',
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          fontWeight: '500',
          padding: '8px 12px',
          transition: 'all 0.1s ease',
          '&:hover': {
            backgroundColor: 'var(--e-bg-hover)',
          },
          '&[data-active]': {
            backgroundColor: 'var(--e-bg-subtle)',
            color: 'var(--e-text-primary)',
            fontWeight: '600',
          },
        },
      },
    },

    ScrollArea: {
      styles: {
        viewport: {
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'var(--e-border)',
            borderRadius: '4px',
          },
        },
      },
    },

    Table: {
      styles: {
        table: {
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
        },
        th: {
          fontFamily: 'var(--e-font-mono)',
          fontSize: 'var(--e-type-xs)',
          fontWeight: '600',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--e-text-secondary)',
          backgroundColor: 'var(--e-bg-subtle)',
          padding: '10px 14px',
          borderBottom: '1px solid var(--e-border)',
        },
        td: {
          padding: '10px 14px',
          borderBottom: '1px solid var(--e-border-subtle)',
          verticalAlign: 'top',
        },
      },
    },

    Code: {
      styles: {
        root: {
          fontFamily: 'var(--e-font-mono)',
          fontSize: 'var(--e-type-sm)',
          backgroundColor: 'var(--e-bg-subtle)',
          border: '1px solid var(--e-border-subtle)',
          padding: '2px 6px',
          borderRadius: 'var(--e-radius-sm)',
        },
      },
    },

    Text: {
      defaultProps: {
        size: 'sm',
      },
    },

    Group: {
      defaultProps: {
        gap: 'sm',
      },
    },

    Stack: {
      defaultProps: {
        gap: 'sm',
      },
    },
  },

  other: {
    version: '2.2.0',
    professional: true,
  },
});