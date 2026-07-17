import Link from "next/link";
import MuiBreadcrumbs from "@mui/material/Breadcrumbs";
import Typography from "@mui/material/Typography";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <MuiBreadcrumbs aria-label="Breadcrumb" separator="/" sx={{ mb: 2, fontSize: "0.85rem" }}>
      {items.map((item, index) =>
        item.href ? (
          <Link key={index} href={item.href} style={{ color: "inherit", textDecoration: "none" }}>
            {item.label}
          </Link>
        ) : (
          <Typography key={index} sx={{ fontWeight: 600, fontSize: "inherit" }} color="text.primary">
            {item.label}
          </Typography>
        )
      )}
    </MuiBreadcrumbs>
  );
}
