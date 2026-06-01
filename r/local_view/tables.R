
library(tidyverse)
library(lubridate)

# df <- readr::read_rds("meetings.rds") ## local
df <- readr::read_rds("/n/holyscratch01/enos_lab/sbarari/localview_data/meetings.rds") ## FASRC cluster

## ++ SUMMARY TABLES ------------------------------------------------------

if ("dat" %in% ls()) {
  df <- dat
  rm(dat)
}

make_tex_table <- function(tbl.df, file.name) {
  tbl.df <- mutate_all(tbl.df, as.character)
  
  # Table header
  c <- length(colnames(tbl.df))
  
  result <- paste0("\\begin{tabular}{",paste0(rep("l",c),collapse=""),"}",
                  "\n\\toprule\n",
                  paste(colnames(tbl.df), collapse=" & "),
                  "\n\\midrule\\\\\n", collapse=" ")
  # Table body
  result <- paste(result,
                  paste(sapply(1:nrow(tbl.df), function(.) paste(tbl.df[.,], collapse=" & ")),
                        collapse="\n"),
                  collapse="\\ \n")
  # Table footer
  result <- paste(result,
                  "\n\\bottomrule",
                  "\n\\end{tabular}",
                  collapse="\\ \n")
  # Printing table
  cat(result)
  writeLines(result, file.name)
  message("\nsaved")
}

tbl_bytype <- df %>% {
    if ("channelType" %in% colnames(.)) rename(., channel_type = channelType)
    else .
  } %>%
  mutate(channel_type = fct_infreq(stringr::str_to_title(channel_type))) %>%
  mutate(channel_type = fct_relevel(channel_type, "Unknown", after = Inf)) %>%
  group_by(`Host Type:` = channel_type) %>%
  summarise(Videos = length(unique(vid_id))) %>%
  mutate(`Videos (\\%)` = sprintf("%0.2f\\%% \\\\ ", (Videos/sum(Videos))*100),
         Videos = scales::comma(Videos))
make_tex_table(tbl_bytype, "table_bytype.tex")

tbl_bygovt <- df %>%
  mutate(place_govt = case_when( ### disaggregate committee
    grepl("county", place_name, ignore.case=T) & grepl("Committee", place_govt, ignore.case=T) ~ "County Committee",
    !grepl("county", place_name, ignore.case=T) & grepl("Committee", place_govt, ignore.case=T) ~ "Municipal Committee",
    TRUE ~ as.character(place_govt)
  )) %>%
  mutate(place_govt = fct_infreq(stringr::str_to_title(place_govt))) %>%
  mutate(place_govt = fct_relevel(place_govt, "Unknown", after = Inf)) %>%
  group_by(`Government Type:` = place_govt) %>%
  summarise(Videos = length(unique(vid_id))) %>%
  mutate(`Videos (\\%)` = sprintf("%0.2f\\%% \\\\ ", (Videos/sum(Videos))*100),
         Videos = scales::comma(Videos))
make_tex_table(tbl_bygovt, "table_bygovt.tex")

tbl_bystate <- df %>%
  filter(!is.na(state_name)) %>%
  group_by(`State:` = state_name) %>%
  summarise(Videos = length(unique(vid_id))) %>%
  mutate(`Videos (\\%)` = sprintf("%0.2f\\%% \\\\ ", (Videos/sum(Videos))*100),
         Videos = scales::comma(Videos))
make_tex_table(tbl_bystate, "table_bystate.tex")

## ++ SPARKLINES TABLE ----------------------------------------------------

### R adapted from ltxsparklines vignette

###################################################
### setup
###################################################
library(ltxsparklines)
library(dtplyr)

options(
  ltxsparklines.width = 10,
  ltxsparklines.clip = FALSE,
  ltxsparklines.na.rm = TRUE,
  ltxsparklines.bottomline = FALSE,
  ltxsparklines.bottomlinex = c(NA, NA),
  ltxsparklines.startdotcolor = NA,
  ltxsparklines.enddotcolor = NA,
  ltxsparklines.dotcolor='blue'
)

###################################################
### fake phrase counts
###################################################

df <- df %>% mutate(month = lubridate::month(meeting_date),
                    year = lubridate::year(meeting_date)) %>% 
  mutate(my = paste0(month, "-", year))

phrase_count <- function(phrase) {
  str_count(df$caption_text_clean, paste0(" ", phrase, " "))
}

all_phrases <- c("climate change", "pandemic", "racism|racist", "affordable housing",
                 "budget cut", "vote by mail|voting by mail", "minimum wage",
                 "sanctuary city", "mass shooting", "gun violence|gun control",
                 "crime", "inflation")

count_mat <- map(all_phrases, phrase_count)
write_rds(count_mat, "out/count_mat.rds")

# count_mat <- sapply(all_phrases, function(phrase) {
#   phrase_count(phrase)
# })

matrix(unlist(count_mat), ncol = 12) %>% dim()

mat <- matrix(unlist(count_mat), ncol = 12)
dim(mat)
colnames(mat) <- all_phrases

df_counts <- as_tibble(mat)

# Proportion of meetings with at least one mention
df_prop <- df %>% 
  bind_cols(df_counts) %>%
  select(year, colnames(df_counts)) %>% 
  group_by(year) %>% 
  summarise_all(~ mean(.x > 0, na.rm = TRUE))

df_prop <- df_prop %>% 
  mutate(year = year) %>% 
  arrange(year)

df_sum <- df %>% 
  bind_cols(df_counts) %>%
  select(year, colnames(df_counts)) %>% 
  group_by(year) %>% 
  summarise_all(sum, na.rm = TRUE)

df_sum <- df_sum %>% 
  mutate(year = year) %>% 
  arrange(year)


###########################################################
### print sparklines: adapted from ltxsparklines vignette
###########################################################
printCount <- function (i) {
  
  col_name <- colnames(df_counts)[i]
  
  vec <- df_prop %>% pull(col_name)
  sum_vec <- df_sum %>% pull(col_name)
  
  sl <- 
    paste0(col_name, " & ", sum(sum_vec), " & ",
           sparkline(vec,
                     width=10,
                     xlim=c(0, length(vec)),
                     ylim=range(vec), 
                     xdots = which(vec == max(vec)),
                     ydots = max(vec),
                     output='knitr'),
           "", " &  placeholder \\\\")
}


#####################################################
### make table: adapted from ltxsparklines vignette
#####################################################
# Table header
result <- paste("\\begin{tabular}{llll}",
                "\\toprule",
                "Phrase & Total Count & Count Over Time & Example Quote\\\\",
                "\\midrule",
                sep="\n")
# Table body
result <- paste(result,
                paste(sapply(1:ncol(df_counts), printCount),
                      collapse="\n"),
                sep="\n")
# Table footer
result <- paste(result,
                "\\bottomrule",
                "\\end{tabular}",
                sep="\n")
# Printing table
write.table(result, file = "table.tex")

