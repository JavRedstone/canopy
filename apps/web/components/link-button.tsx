"use client";

import Link from "next/link";
import Button, { ButtonProps } from "@mui/material/Button";

/** MUI's `component={Link}` polymorphic pattern only works inside a Client Component
 *  file -- passed in from a Server Component, the `component` prop is a bare function
 *  reference React can't serialize across the RSC boundary. This wraps it once so
 *  Server Component pages can use a plain, serializable-props link button. */
export function LinkButton({ href, ...props }: ButtonProps & { href: string }) {
  return <Button component={Link} href={href} {...props} />;
}
