import { createTheme, type MantineColorsTuple } from '@mantine/core';

/* ─── Brand Color — Electric Indigo ─── */
const brand: MantineColorsTuple = [
  '#EEF2FF', // 0 - lightest
  '#E0E7FF', // 1
  '#C7D2FE', // 2
  '#A5B4FC', // 3
  '#818CF8', // 4
  '#6366F1', // 5
  '#4F46E5', // 6 ← primary
  '#4338CA', // 7
  '#3730A3', // 8
  '#312E81', // 9 - darkest
];

/* ─── E.sapiens Theme v3 ─── */
export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: 6,

  colors: { brand },

  fontFamily: "var(--e-font-sans)",
  fontFamilyMonospace: "var(--e-font-mono)",

  headings: {
    fontFamily: "var(--e-font-display)",
    fontWeight: '600',
    sizes: {
      h1: { fontSize: 'var(--e-type-2xl)', lineHeight: '1.2' },
      h2: { fontSize: 'var(--e-type-xl)', lineHeight: '1.25' },
      h3: { fontSize: 'var(--e-type-lg)', lineHeight: '1.3' },
      h4: { fontSize: 'var(--e-type-base)', lineHeight: '1.35' },
      h5: { fontSize: 'var(--e-type-sm)', fontWeight: '600' },
      h6: { fontSize: 'var(--e-type-xs)', fontWeight: '600' },
    },
  },

  fontSizes: {
    xs: 'var(--e-type-xs)',
    sm: 'var(--e-type-sm)',
    md: 'var(--e-type-base)',
    lg: 'var(--e-type-md)',
    xl: 'var(--e-type-xl)',
  },

  spacing: {
    xs: '4px', sm: '8px', md: '12px', lg: '16px', xl: '20px',
  },

  radius: {
    xs: '6px', sm: '8px', md: '10px', lg: '14px', xl: '18px',
  },

  defaultRadius: 'lg',
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
      defaultProps: { p: 'md', radius: 'lg' },
      styles: {
        root: {
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border-subtle)',
          boxShadow: 'var(--e-shadow-sm)',
        },
      },
    },

    Card: {
      defaultProps: { p: 'lg', radius: 'xl', withBorder: true },
      styles: {
        root: {
          backgroundColor: 'var(--e-bg-surface)',
          borderColor: 'var(--e-border-subtle)',
          boxShadow: 'var(--e-shadow-card)',
          transition: 'box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease',
        },
      },
    },

    Button: {
      defaultProps: { radius: 'lg', size: 'sm' },
      styles: {
        root: {
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          fontWeight: '500',
          transition: 'all 0.12s cubic-bezier(0.4, 0, 0.2, 1)',
          height: '42px',
          letterSpacing: '-0.01em',
        },
      },
    },

    ActionIcon: {
      defaultProps: { radius: 'md', variant: 'subtle' },
      styles: {
        root: {
          transition: 'all 0.12s ease',
        },
      },
    },

    TextInput: {
      defaultProps: { radius: 'lg', size: 'sm' },
      styles: {
        input: {
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border)',
          color: 'var(--e-text-primary)',
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-base)',
          padding: '11px 14px',
          height: '44px',
          transition: 'border-color 0.12s ease, box-shadow 0.12s ease',
          '&:focus': {
            borderColor: 'var(--e-brand)',
            boxShadow: '0 0 0 4px rgba(79, 70, 229, 0.1)',
          },
          '&::placeholder': {
            color: 'var(--e-text-muted)',
          },
        },
      },
    },

    Badge: {
      defaultProps: { radius: 'sm', variant: 'light' },
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
      defaultProps: { withArrow: true, arrowSize: 6, radius: 'sm' },
      styles: {
        tooltip: {
          fontFamily: 'var(--e-font-mono)',
          fontSize: 'var(--e-type-xs)',
          fontWeight: '500',
          letterSpacing: '0.03em',
          padding: '6px 10px',
          backgroundColor: '#111827',
        },
      },
    },

    Modal: {
      defaultProps: { radius: 'xl', centered: true },
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
          borderRadius: 'var(--e-radius-lg)',
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          fontWeight: '500',
          padding: '9px 14px',
          transition: 'all 0.12s ease',
          '&:hover': {
            backgroundColor: 'var(--e-bg-hover)',
          },
          '&[data-active]': {
            backgroundColor: 'var(--e-bg-subtle)',
            color: 'var(--e-brand)',
            fontWeight: '600',
          },
        },
      },
    },

    ScrollArea: {
      styles: {
        viewport: {
          '&::-webkit-scrollbar': { width: '5px' },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: 'var(--e-border)',
            borderRadius: '9999px',
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

    Text: { defaultProps: { size: 'sm' } },
    Group: { defaultProps: { gap: 'sm' } },
    Stack: { defaultProps: { gap: 'sm' } },
  },

  other: {
    version: '3.0',
    designSystem: 'modern-minimal-luxury',
  },
});