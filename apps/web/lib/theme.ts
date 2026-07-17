import { createTheme } from "@mui/material/styles";

const fontFamily = 'var(--font-google-sans), -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

export const theme = createTheme({
  cssVariables: true,
  palette: {
    mode: "light",
    primary: { main: "#0a0a0a", contrastText: "#ffffff" },
    error: { main: "#b3261e" },
    background: { default: "#fafafa", paper: "#ffffff" },
    divider: "#e6e6e6",
    text: { primary: "#0a0a0a", secondary: "#6b6b6b" }
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily,
    button: { textTransform: "none", fontWeight: 600 }
  }
});

// A dark variant scoped to the coding-lab workspace subtree (Monaco panes, console,
// file tabs), which keeps its own fixed dark theme regardless of the app's light theme.
export const labTheme = createTheme({
  cssVariables: { cssVarPrefix: "lab" },
  palette: {
    mode: "dark",
    primary: { main: "#4f9cff" },
    success: { main: "#2dbf7c" },
    error: { main: "#e5534b" },
    background: { default: "#1e1e1e", paper: "#181818" }
  },
  shape: { borderRadius: 8 },
  typography: { fontFamily, button: { textTransform: "none", fontWeight: 600 } }
});
