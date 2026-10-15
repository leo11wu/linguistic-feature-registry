args <- commandArgs(trailingOnly=TRUE)
library(zipfR)
tab <- read.table(file("stdin"), header=TRUE)
model <- if (length(args)) args[[1]] else "fzm"
stopifnot(model %in% c("fzm", "zm", "gigp"), nrow(tab)>=3, all(tab$m>0), all(tab$Vm>0))
spectrum <- spc(m=tab$m, Vm=tab$Vm)
fit <- lnre(model, spectrum)
params <- fit$param
stopifnot(length(params)>0, all(is.finite(unlist(params))))
parts <- vapply(names(params), function(name) paste0('"',name,'":',format(params[[name]],digits=16,scientific=TRUE)), character(1))
cat('{"model":"',model,'","method":"zipfR-0.6-70","parameters":{',paste(parts,collapse=','),'}}\n',sep='')
