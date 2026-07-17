"use client";

import { createContext, useContext, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { BrandLink } from "@/components/brand-link";
import { SignOutButton } from "@/components/sign-out-button";

const SetFullBleedContext = createContext<(fullBleed: boolean) => void>(() => {});

/** Lets immersive learning screens claim the viewport below the lightweight header. */
export function useFullBleed(fullBleed: boolean) {
  const setFullBleed = useContext(SetFullBleedContext);
  useEffect(() => {
    setFullBleed(fullBleed);
    return () => setFullBleed(false);
  }, [fullBleed, setFullBleed]);
}

export function AppShell({ email, children }: { email: string; children: React.ReactNode }) {
  const [fullBleed, setFullBleed] = useState(false);

  return (
    <SetFullBleedContext.Provider value={setFullBleed}>
      <Box sx={{ minHeight: "100vh", height: fullBleed ? "100vh" : undefined, overflow: fullBleed ? "hidden" : undefined }}>
        <Stack component="header" direction="row" sx={{ position: "sticky", top: 0, zIndex: 3, height: 64, px: { xs: 2, sm: 3 }, alignItems: "center", justifyContent: "space-between", borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
          <BrandLink />
          <Stack direction="row" sx={{ alignItems: "center", gap: 1.25 }}>
            <Typography variant="body2" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>{email}</Typography>
            <SignOutButton />
          </Stack>
        </Stack>
        <Box
          component="main"
          sx={{
            minWidth: 0,
            overflowX: "hidden",
            display: fullBleed ? "flex" : undefined,
            flexDirection: fullBleed ? "column" : undefined,
            height: fullBleed ? "calc(100vh - 64px)" : undefined,
            overflow: fullBleed ? "hidden" : undefined
          }}
        >
          {children}
        </Box>
      </Box>
    </SetFullBleedContext.Provider>
  );
}
