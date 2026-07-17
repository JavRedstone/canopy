import { redirect } from "next/navigation";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { AppShell } from "@/components/app-shell";
import { Icon } from "@/components/icon";
import { SidebarNav } from "@/components/sidebar-nav";
import { SignOutButton } from "@/components/sign-out-button";
import { BrandLink } from "@/components/brand-link";
import { LinkButton } from "@/components/link-button";
import { createClient } from "@/lib/supabase/server";

export default async function CoursesLayout({ children }: LayoutProps<"/courses">) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <AppShell
      sidebar={
        <>
          <BrandLink />
          <LinkButton href="/courses/new" variant="contained" startIcon={<Icon name="add" />} sx={{ justifyContent: "flex-start" }}>
            New course
          </LinkButton>
          <SidebarNav />
          <Stack sx={{ gap: 1, fontSize: "0.82rem", pt: 1.5, borderTop: 1, borderColor: "divider" }}>
            <Typography variant="body2" color="text.secondary" noWrap>{user.email}</Typography>
            <SignOutButton />
          </Stack>
        </>
      }
    >
      {children}
    </AppShell>
  );
}
