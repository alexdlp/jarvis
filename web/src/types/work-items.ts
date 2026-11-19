// Fields  required to display a work item in a list.
// The backend may return additional fields.
export type WorkItemSummary = {
    id: string;
    title: string;
    kind: "idea" | "task" | "project";
    status: "inbox" | "active" | "parked" | "done" | "cancelled";
};

// Data returned by the capture_workitem tool.
export type CaptureWorkItemResult = {
    item: WorkItemSummary;
    items: WorkItemSummary[] | null;
    list_error: string | null;
};