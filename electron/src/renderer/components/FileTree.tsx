import { useCallback, useRef, useState, useEffect } from 'react'
import { Tree, NodeRendererProps } from 'react-arborist'
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, RefreshCw } from 'lucide-react'
import { useAppStore, FileNode } from '../stores/app-store'
import clsx from 'clsx'

function Node({ node, style, dragHandle }: NodeRendererProps<FileNode>) {
  const { selectedFile, setSelectedFile, setFileContent, setIsDirty } = useAppStore()
  const isSelected = selectedFile === node.data.path

  const handleClick = useCallback(async () => {
    if (node.data.isFolder) {
      node.toggle()
    } else {
      // Load file content
      const result = await window.api.files.read(node.data.path)
      if (result.success) {
        setSelectedFile(node.data.path)
        setFileContent(result.content)
        setIsDirty(false)
      }
    }
  }, [node, setSelectedFile, setFileContent, setIsDirty])

  return (
    <div
      ref={dragHandle}
      style={style}
      className={clsx(
        'flex items-center gap-1.5 px-2 py-1 cursor-pointer text-sm',
        'hover:bg-border/50 transition-colors',
        isSelected && 'bg-accent/30'
      )}
      onClick={handleClick}
    >
      {/* Expand/collapse arrow for folders */}
      {node.data.isFolder ? (
        <span className="w-4 text-text-secondary">
          {node.isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      ) : (
        <span className="w-4" />
      )}

      {/* Icon */}
      <span className="text-text-secondary">
        {node.data.isFolder ? (
          node.isOpen ? (
            <FolderOpen size={16} className="text-yellow-500" />
          ) : (
            <Folder size={16} className="text-yellow-500" />
          )
        ) : (
          <File size={16} className="text-blue-400" />
        )}
      </span>

      {/* Name */}
      <span className="truncate">{node.data.name}</span>
    </div>
  )
}

export function FileTree() {
  const { fileTree, refreshFileTree, outputDir } = useAppStore()
  const containerRef = useRef<HTMLDivElement>(null)
  const [treeHeight, setTreeHeight] = useState(400)

  // Observe container size changes for dynamic tree height
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateHeight = () => {
      setTreeHeight(container.clientHeight)
    }

    updateHeight()

    const observer = new ResizeObserver(updateHeight)
    observer.observe(container)

    return () => observer.disconnect()
  }, [])

  return (
    <div className="h-full flex flex-col bg-sidebar-bg border-r border-border overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold uppercase text-text-secondary">
          Output Files
        </span>
        <button
          onClick={refreshFileTree}
          className="p-1 hover:bg-border rounded text-text-secondary hover:text-text-primary"
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Tree */}
      <div ref={containerRef} className="flex-1 min-h-0 overflow-hidden py-1">
        {fileTree.length === 0 ? (
          <div className="px-3 py-4 text-sm text-text-secondary text-center">
            <p>No output files yet.</p>
            <p className="mt-1 text-xs">
              Process a video to generate transcripts.
            </p>
          </div>
        ) : (
          <Tree<FileNode>
            data={fileTree}
            openByDefault={false}
            width="100%"
            height={treeHeight}
            indent={16}
            rowHeight={28}
            overscanCount={5}
          >
            {Node}
          </Tree>
        )}
      </div>

      {/* Footer with path */}
      {outputDir && (
        <div className="flex-shrink-0 px-3 py-1.5 border-t border-border text-xs text-text-secondary truncate">
          {outputDir}
        </div>
      )}
    </div>
  )
}
