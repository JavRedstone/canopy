"use client";

import { createContext, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import { BrandLink } from "@/components/brand-link";
import { LinkButton } from "@/components/link-button";
import { CONTENT_PX } from "@/components/page-shell";
import { ProfileNameButton } from "@/components/profile-name-button";
import { SignOutButton } from "@/components/sign-out-button";

const SetFullBleedContext = createContext<(fullBleed: boolean) => void>(() => {});

const NAV_LINKS = [
  { label: "My Courses", href: "/courses" },
  { label: "Playground", href: "/courses/playground" }
];

/** Lets immersive learning screens claim the viewport below the lightweight header. */
export function useFullBleed(fullBleed: boolean) {
  const setFullBleed = useContext(SetFullBleedContext);
  useEffect(() => {
    setFullBleed(fullBleed);
    return () => setFullBleed(false);
  }, [fullBleed, setFullBleed]);
}

/** `email` is omitted for signed-out visitors (the landing page), who get a Sign in button
 *  instead of the profile controls. Everything else about the header stays identical so the
 *  marketing page and the app can't drift apart. */
export function AppShell({ email, children }: { email?: string; children: React.ReactNode }) {
  const [fullBleed, setFullBleed] = useState(false);
  const pathname = usePathname();
  // The playground sits under /courses, so it has to be claimed first -- otherwise it lights
  // both tabs. Everything else in the subtree (a course, a concept, the new-course form)
  // counts as My Courses, which is the area those pages belong to.
  const playgroundActive = pathname === "/courses/playground";
  const isActive = (href: string) =>
    href === "/courses/playground" ? playgroundActive : pathname.startsWith("/courses") && !playgroundActive;

  return (
    <SetFullBleedContext.Provider value={setFullBleed}>
      <Box sx={{ minHeight: "100vh", height: fullBleed ? "100vh" : undefined, overflow: fullBleed ? "hidden" : undefined }}>
        {/* Three columns, full-bleed across the viewport. The outer tracks are equal 1fr
            so the nav sits on the true centre of the header rather than drifting with
            whatever the brand and account clusters happen to measure. */}
        <Box component="header" sx={{ position: "sticky", top: 0, zIndex: 3, borderBottom: 1, borderColor: "divider", bgcolor: "background.paper" }}>
          <Box
            sx={{
              height: 64,
              px: CONTENT_PX,
              display: "grid",
              gridTemplateColumns: "1fr auto 1fr",
              alignItems: "center",
              columnGap: 2
            }}
          >
            <Box sx={{ justifySelf: "start", minWidth: 0 }}>
              <BrandLink />
            </Box>

            {/* Signed-out visitors would only be bounced to /login by these, so they stay
                hidden -- but the column still has to be occupied to keep the account
                cluster in track three. */}
            {email ? (
              <Stack
                component="nav"
                direction="row"
                sx={{ justifySelf: "center", display: { xs: "none", sm: "flex" }, alignItems: "center", gap: 0.25 }}
              >
                {NAV_LINKS.map((link) => {
                  const active = isActive(link.href);
                  return (
                    <Button
                      key={link.href}
                      component={Link}
                      href={link.href}
                      size="small"
                      aria-current={active ? "page" : undefined}
                      sx={{
                        px: 1.25,
                        whiteSpace: "nowrap",
                        color: active ? "text.primary" : "text.secondary",
                        fontWeight: active ? 700 : 500,
                        bgcolor: active ? "action.selected" : "transparent"
                      }}
                    >
                      {link.label}
                    </Button>
                  );
                })}
              </Stack>
            ) : (
              <Box />
            )}

            <Box sx={{ justifySelf: "end" }}>
              {email ? (
                <Stack direction="row" sx={{ alignItems: "center", gap: 1.25 }}>
                  <ProfileNameButton email={email} />
                  <SignOutButton />
                </Stack>
              ) : (
                <LinkButton href="/login" variant="outlined">Sign in</LinkButton>
              )}
            </Box>
          </Box>
        </Box>
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
