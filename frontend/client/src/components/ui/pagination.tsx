/* eslint-disable react/require-default-props */
import * as React from "react"
import {
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
} from "lucide-react"

import { cn } from "@/lib/utils"
import {
  ButtonProps,
  buttonVariants,
} from "@/components/ui/button"

/* ------------------------------------------------------------------ */
/*  Root <Pagination> container                                       */
/* ------------------------------------------------------------------ */
export const Pagination = ({
  className,
  ...props
}: React.ComponentProps<"nav">) => (
  <nav
    role="navigation"
    aria-label="pagination"
    className={cn("mx-auto flex w-full justify-center", className)}
    {...props}
  />
)
Pagination.displayName = "Pagination"

/* ------------------------------------------------------------------ */
export const PaginationContent = React.forwardRef<
  HTMLUListElement,
  React.ComponentProps<"ul">
>(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    className={cn("flex flex-row items-center gap-1", className)}
    {...props}
  />
))
PaginationContent.displayName = "PaginationContent"

/* ------------------------------------------------------------------ */
export const PaginationItem = React.forwardRef<
  HTMLLIElement,
  React.ComponentProps<"li">
>(({ className, ...props }, ref) => (
  <li ref={ref} className={cn("", className)} {...props} />
))
PaginationItem.displayName = "PaginationItem"

/* ------------------------------------------------------------------ */
/*  Generic page / numbered link                                      */
/* ------------------------------------------------------------------ */
type PaginationLinkProps = {
  isActive?: boolean
} & Pick<ButtonProps, "size"> &
  React.ComponentProps<"a">

export const PaginationLink = ({
  className,
  isActive,
  size = "icon",
  ...props
}: PaginationLinkProps) => (
  /* using <a> keeps the component un-opinionated about router */
  <a
    aria-current={isActive ? "page" : undefined}
    className={cn(
      buttonVariants({
        variant: isActive ? "outline" : "ghost",
        size,
      }),
      className,
    )}
    {...props}
  />
)
PaginationLink.displayName = "PaginationLink"

/* ------------------------------------------------------------------ */
/*  Previous / Next convenience wrappers                              */
/* ------------------------------------------------------------------ */
type NavLinkProps = React.ComponentProps<typeof PaginationLink> & {
  disabled?: boolean
}

export const PaginationPrevious = ({
  className,
  disabled,
  ...props
}: NavLinkProps) => (
  <PaginationLink
    aria-label="Go to previous page"
    size="default"
    aria-disabled={disabled}
    tabIndex={disabled ? -1 : undefined}
    className={cn(
      "gap-1 pl-2.5",
      disabled && "pointer-events-none opacity-50",
      className,
    )}
    {...props}
  >
    <ChevronLeft className="h-4 w-4" />
    <span>Previous</span>
  </PaginationLink>
)
PaginationPrevious.displayName = "PaginationPrevious"

export const PaginationNext = ({
  className,
  disabled,
  ...props
}: NavLinkProps) => (
  <PaginationLink
    aria-label="Go to next page"
    size="default"
    aria-disabled={disabled}
    tabIndex={disabled ? -1 : undefined}
    className={cn(
      "gap-1 pr-2.5",
      disabled && "pointer-events-none opacity-50",
      className,
    )}
    {...props}
  >
    <span>Next</span>
    <ChevronRight className="h-4 w-4" />
  </PaginationLink>
)
PaginationNext.displayName = "PaginationNext"

/* ------------------------------------------------------------------ */
/*  Ellipsis when list is truncated                                   */
/* ------------------------------------------------------------------ */
export const PaginationEllipsis = ({
  className,
  ...props
}: React.ComponentProps<"span">) => (
  <span
    aria-hidden
    className={cn("flex h-9 w-9 items-center justify-center", className)}
    {...props}
  >
    <MoreHorizontal className="h-4 w-4" />
    <span className="sr-only">More pages</span>
  </span>
)
PaginationEllipsis.displayName = "PaginationEllipsis"

/* ------------------------------------------------------------------ */
/*  NEW: “Page X of N” status node                                    */
/* ------------------------------------------------------------------ */
interface PaginationStatusProps {
  currentPage: number
  totalPages: number
  className?: string
}
export const PaginationStatus = ({
  currentPage,
  totalPages,
  className,
}: PaginationStatusProps) => (
  <span
    className={cn(
      "px-2 text-sm text-muted-foreground select-none",
      className,
    )}
  >
    Page&nbsp;{currentPage}&nbsp;of&nbsp;{totalPages}
  </span>
)
PaginationStatus.displayName = "PaginationStatus"